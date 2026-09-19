"""
yq: Command-line YAML processor - jq wrapper for YAML documents

yq transcodes YAML documents to JSON and passes them to jq.
See https://github.com/kislyuk/yq for more information.
"""

# PYTHON_ARGCOMPLETE_OK

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import ExitStack
from datetime import date, datetime, time
from itertools import chain, islice
from typing import List

import argcomplete
import yaml

from .dumper import get_dumper
from .loader import get_loader
from .parser import get_parser, jq_arg_spec
from .toml_support import tomlkit_from_json, tomlkit_to_json

try:
    from .version import version as __version__
except ImportError:
    __version__ = "0.0.0"


class JSONDateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


def decode_docs(jq_output, json_decoder):
    while jq_output:
        doc, pos = json_decoder.raw_decode(jq_output)
        jq_output = jq_output[pos + 1 :]
        yield doc


def get_toml_loader():
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads
    else:
        import tomlkit

        return tomlkit.parse


def xq_cli():
    cli(input_format="xml", program_name="xq")


def tq_cli():
    cli(input_format="toml", program_name="tomlq")


def cli(args=None, input_format="yaml", program_name="yq"):
    parser = get_parser(program_name, __doc__)
    argcomplete.autocomplete(parser)
    args, jq_args = parser.parse_known_args(args=args)
    null_input = False

    for i, arg in enumerate(jq_args):
        if arg == "--null-input":
            null_input = True
        if arg.startswith("-") and not arg.startswith("--"):
            if "n" in arg:
                null_input = True
            if "i" in arg:
                args.in_place = True
            if "F" in arg:
                args.yaml_frontmatter = True
            if "y" in arg:
                args.output_format = "yaml"
            elif "Y" in arg:
                args.output_format = "annotated_yaml"
            elif "t" in arg:
                args.output_format = "toml"
            elif "T" in arg:
                args.output_format = "annotated_toml"
            elif "x" in arg:
                args.output_format = "xml"
            jq_args[i] = (
                arg.replace("i", "")
                .replace("x", "")
                .replace("y", "")
                .replace("Y", "")
                .replace("t", "")
                .replace("T", "")
                .replace("F", "")
            )
        if args.output_format != "json":
            jq_args[i] = jq_args[i].replace("C", "")
            if jq_args[i] == "-":
                jq_args[i] = None

    jq_args = [arg for arg in jq_args if arg is not None]

    for arg in jq_arg_spec:
        values = vars(args).pop(arg)
        if values is not None:
            for value_group in values:
                jq_args.append(arg)
                jq_args.extend(value_group)
    with ExitStack() as input_stack:
        if args.jq_filter is not None:
            if "--from-file" in jq_args or "-f" in jq_args:
                args.input_streams.insert(0, argparse.FileType()(args.jq_filter))
            else:
                jq_filter_arg_loc = len(jq_args)
                if "--args" in jq_args:
                    jq_filter_arg_loc = jq_args.index("--args") + 1
                elif "--jsonargs" in jq_args:
                    jq_filter_arg_loc = jq_args.index("--jsonargs") + 1
                jq_args.insert(jq_filter_arg_loc, args.jq_filter)
                if null_input:
                    args.input_streams.insert(0, input_stack.enter_context(open(os.devnull)))
        delattr(args, "jq_filter")
        in_place = args.in_place
        delattr(args, "in_place")

        if (sys.stdin is None or sys.stdin.isatty()) and not args.input_streams:
            parser.print_help()
            sys.exit(2)
        elif not args.input_streams:
            args.input_streams = [sys.stdin]

        yq_args = dict(input_format=input_format, program_name=program_name, jq_args=jq_args, **vars(args))
        if in_place:
            if args.output_format not in {"yaml", "annotated_yaml", "toml", "annotated_toml", "xml"}:
                sys.exit(f"{program_name}: -i/--in-place can only be used with -y/-Y/-t/-T/-x")
            input_streams = yq_args.pop("input_streams")
            if len(input_streams) == 1 and input_streams[0].name == "<stdin>":
                msg = "{}: -i/--in-place can only be used with filename arguments, not on standard input"
                sys.exit(msg.format(program_name))
            for i, input_stream in enumerate(input_streams):

                def exit_handler(arg=None):
                    if arg:
                        sys.exit(arg)

                if i < len(input_streams):
                    yq_args["exit_func"] = exit_handler

                with io.StringIO() as out_fh:
                    yq(input_streams=[input_stream], output_stream=out_fh, **yq_args)
                    with open(input_stream.name, "w", newline="" if args.yaml_frontmatter else None) as fh:
                        fh.write(out_fh.getvalue())
        else:
            yq(**yq_args)


def load_yaml_docs(in_stream, out_stream, jq, loader_class, max_expansion_factor, exit_func, prog):
    loader = loader_class(in_stream)

    last_loader_pos = 0
    doc_count = 0
    try:
        while loader.check_node():
            node = loader.get_node()
            doc = loader.construct_document(node)
            loader_pos = node.end_mark.index
            doc_len = loader_pos - last_loader_pos
            doc_bytes_written = 0
            for chunk in JSONDateTimeEncoder().iterencode(doc):
                doc_bytes_written += len(chunk)
                if doc_bytes_written > doc_len * max_expansion_factor:
                    if jq:
                        jq.kill()
                    exit_func(f"{prog}: Error: detected unsafe YAML entity expansion")
                out_stream.write(chunk)
            out_stream.write("\n")
            last_loader_pos = loader_pos
            doc_count += 1
    finally:
        loader.dispose()
    return doc_count


def has_explicit_yaml_start(source, loader_class):
    # Inspect only the stream/document start events, including comments and directives.
    events = yaml.parse(source, Loader=loader_class)
    try:
        next(events)  # StreamStartEvent
        event = next(events)
        return isinstance(event, yaml.events.DocumentStartEvent) and event.explicit
    finally:
        events.close()


def read_yaml_frontmatter(stream):
    """Buffer the header and closing fence, leaving the body unread in stream."""
    lines: list[str] = []
    started = False
    for line in stream:
        content = line.rstrip("\r\n")
        if not lines:
            content = content.lstrip("\ufeff")
        marker = re.match(r"(---|\.\.\.)(?=[ \t]|$)", content)
        if marker:
            if marker[1] == "---" and not started:
                started = True
            else:
                return "".join(lines), line
        elif content.strip() and not content.lstrip().startswith(("#", "%")):
            started = True
        lines.append(line)
    return "".join(lines), ""


def yq(
    input_streams=None,
    output_stream=None,
    input_format="yaml",
    output_format="json",
    program_name="yq",
    width=None,
    indentless_lists=False,
    xml_root=None,
    xml_item_depth=0,
    xml_dtd=False,
    xml_force_list=frozenset(),
    xml_short_empty_elements=False,
    explicit_start=False,
    explicit_end=False,
    expand_merge_keys=True,
    expand_aliases=True,
    max_expansion_factor=1024,
    yaml_output_grammar_version="1.1",
    jq_args=frozenset(),
    exit_func=None,
    yaml_frontmatter=False,
):
    if not input_streams:
        input_streams = [sys.stdin]
    if not output_stream:
        output_stream = sys.stdout
    if not exit_func:
        exit_func = sys.exit
    converting_output = output_format != "json"

    if yaml_frontmatter:
        if input_format != "yaml" or output_format not in {"json", "yaml", "annotated_yaml"}:
            exit_func(f"{program_name}: --yaml-frontmatter requires YAML input and JSON or YAML output")
            return
        if converting_output and len(input_streams) != 1:
            exit_func(f"{program_name}: --yaml-frontmatter requires one input file, or --in-place for multiple files")
            return
        for stream in [*input_streams, output_stream]:
            if isinstance(stream, io.TextIOWrapper):
                stream.reconfigure(newline="")

    try:
        # Notes: universal_newlines is just a way to induce subprocess to make stdin a text buffer and encode it for us;
        # close_fds must be false for command substitution to work (yq . t.yml --slurpfile t <(yq . t.yml))
        jq = subprocess.Popen(
            ["jq"] + list(jq_args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE if converting_output else None,
            close_fds=False,
            universal_newlines=True,
        )
    except OSError as e:
        msg = "{}: Error starting jq: {}: {}. Is jq installed and available on PATH?"
        exit_func(msg.format(program_name, type(e).__name__, e))

    assert jq.stdin is not None  # this is to keep mypy happy

    try:
        if converting_output:
            # TODO: enable true streaming in this branch (with asyncio, asyncproc, a multi-shot variant of
            # subprocess.Popen._communicate, etc.)
            # See https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
            use_annotations = output_format == "annotated_yaml"
            use_toml_annotations = output_format == "annotated_toml"
            json_buffer = io.StringIO()
            input_doc_count = 0
            yaml_boundary = ""
            for input_stream in input_streams:
                if input_format == "yaml":
                    loader_class = get_loader(
                        use_annotations=use_annotations,
                        expand_aliases=expand_aliases,
                        expand_merge_keys=expand_merge_keys,
                    )
                    if yaml_frontmatter:
                        yaml_input, yaml_boundary = read_yaml_frontmatter(input_stream)
                    else:
                        yaml_input = input_stream.read()
                    explicit_start = explicit_start or has_explicit_yaml_start(yaml_input, loader_class)
                    input_doc_count += load_yaml_docs(
                        in_stream=io.StringIO(yaml_input),
                        out_stream=json_buffer,
                        jq=None,
                        loader_class=loader_class,
                        max_expansion_factor=max_expansion_factor,
                        exit_func=exit_func,
                        prog=program_name,
                    )
                elif input_format == "xml":
                    import xmltodict

                    if xml_item_depth != 0:
                        raise ValueError("xml_item_depth is not supported with xq -x")

                    xml_doc = xmltodict.parse(
                        input_stream.buffer if isinstance(input_stream, io.TextIOWrapper) else input_stream.read(),
                        disable_entities=True,
                        force_list=xml_force_list,
                    )
                    json.dump(xml_doc, json_buffer, cls=JSONDateTimeEncoder)
                    json_buffer.write("\n")
                elif input_format == "toml":
                    import tomlkit

                    toml_doc = tomlkit.load(input_stream)
                    json.dump(
                        tomlkit_to_json(toml_doc, use_annotations=use_toml_annotations),
                        json_buffer,
                        cls=JSONDateTimeEncoder,
                    )
                    json_buffer.write("\n")
                else:
                    raise ValueError("Unknown input format")
            jq_out, _jq_err = jq.communicate(json_buffer.getvalue())
            if yaml_frontmatter and jq.returncode:
                for input_stream in input_streams:
                    input_stream.close()
                exit_func(jq.returncode)
                return
            json_decoder = json.JSONDecoder()
            if output_format == "yaml" or output_format == "annotated_yaml":
                dumper_class = get_dumper(
                    use_annotations=use_annotations,
                    indentless=indentless_lists,
                    grammar_version=yaml_output_grammar_version,
                )
                docs = decode_docs(jq_out, json_decoder)
                first_docs = list(islice(docs, 2))
                if yaml_frontmatter and len(first_docs) != 1:
                    raise ValueError("--yaml-frontmatter requires the jq filter to produce exactly one document")
                yaml_output = io.StringIO() if yaml_boundary else output_stream
                yaml.dump_all(
                    chain(first_docs, docs),
                    stream=yaml_output,
                    Dumper=dumper_class,
                    width=sys.maxsize if width == 0 else width,
                    allow_unicode=True,
                    default_flow_style=False,
                    explicit_start=explicit_start or input_doc_count > 1 or len(first_docs) > 1 or bool(yaml_boundary),
                    explicit_end=explicit_end,
                )
                if yaml_boundary:
                    rendered_yaml = yaml_output.getvalue()
                    # The original closing fence terminates even a scalar document.
                    if rendered_yaml.endswith("...\n") and (not explicit_end or yaml_boundary.startswith("...")):
                        rendered_yaml = rendered_yaml[:-4]
                    output_stream.write(rendered_yaml)
                    output_stream.write(yaml_boundary)
                    shutil.copyfileobj(input_streams[0], output_stream, length=64 * 1024)
            elif output_format == "xml":
                import xmltodict

                for doc in decode_docs(jq_out, json_decoder):
                    if xml_root:
                        doc = {xml_root: doc}
                    elif not isinstance(doc, dict):
                        msg = (
                            "{}: Error converting JSON to XML: cannot represent non-object types at top level. "
                            "Use --xml-root=name to envelope your output with a root element."
                        )
                        exit_func(msg.format(program_name))
                    full_document = bool(xml_dtd)
                    try:
                        xmltodict.unparse(
                            doc,
                            output=output_stream,
                            full_document=full_document,
                            pretty=True,
                            indent="  ",
                            short_empty_elements=xml_short_empty_elements,
                        )
                    except ValueError as e:
                        if "Document must have exactly one root" in str(e):
                            raise ValueError(
                                str(e) + " Use --xml-root=name to envelope your output with a root element"
                            ) from e
                        else:
                            raise
                    output_stream.write("\n")
            elif output_format == "toml" or output_format == "annotated_toml":
                import tomlkit

                for doc in decode_docs(jq_out, json_decoder):
                    if not isinstance(doc, dict):
                        msg = "{}: Error converting JSON to TOML: cannot represent non-object types at top level."
                        exit_func(msg.format(program_name))
                    if output_format == "annotated_toml":
                        doc = tomlkit_from_json(doc)
                    tomlkit.dump(doc, output_stream)
            else:
                raise ValueError("Unknown output format")
        else:
            if input_format == "yaml":
                loader_class = get_loader(
                    use_annotations=False, expand_aliases=expand_aliases, expand_merge_keys=expand_merge_keys
                )
                for input_stream in input_streams:
                    yaml_stream = input_stream
                    if yaml_frontmatter:
                        yaml_stream = io.StringIO(read_yaml_frontmatter(input_stream)[0])
                    load_yaml_docs(
                        in_stream=yaml_stream,
                        out_stream=jq.stdin,
                        jq=jq,
                        loader_class=loader_class,
                        max_expansion_factor=max_expansion_factor,
                        exit_func=exit_func,
                        prog=program_name,
                    )
            elif input_format == "xml":
                import xmltodict

                def emit_entry(path, entry):
                    assert jq.stdin is not None  # this is to keep mypy happy
                    json.dump(entry, jq.stdin)
                    jq.stdin.write("\n")
                    return True

                for input_stream in input_streams:
                    xml_doc = xmltodict.parse(
                        input_stream.buffer if isinstance(input_stream, io.TextIOWrapper) else input_stream.read(),
                        disable_entities=True,
                        force_list=xml_force_list,
                        item_depth=xml_item_depth,
                        item_callback=emit_entry,
                    )
                    if xml_doc:
                        emit_entry(None, xml_doc)
            elif input_format == "toml":
                toml_loader = get_toml_loader()
                for input_stream in input_streams:
                    toml_doc = toml_loader(input_stream.read())
                    json.dump(toml_doc, jq.stdin, cls=JSONDateTimeEncoder)
                    jq.stdin.write("\n")
            else:
                raise ValueError("Unknown input format")

            try:
                jq.stdin.close()
            except Exception:
                pass
            jq.wait()
        for input_stream in input_streams:
            input_stream.close()
        exit_func(jq.returncode)
    except Exception as e:
        exit_func(f"{program_name}: Error running jq: {type(e).__name__}: {e}.")
