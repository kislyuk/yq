"""
yq: Command-line YAML processor - jq wrapper for YAML documents

yq transcodes YAML documents to JSON and passes them to jq.
See https://github.com/kislyuk/yq for more information.
"""

# PYTHON_ARGCOMPLETE_OK

import argparse
import io
import json
import os
import subprocess
import sys
from datetime import date, datetime, time

import argcomplete
import yaml

from .dumper import get_dumper
from .loader import get_loader
from .parser import get_parser, jq_arg_spec

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


def xq_cli():
    cli(input_format="xml", program_name="xq")


def tq_cli():
    cli(input_format="toml", program_name="tomlq")


class DeferredOutputStream:
    def __init__(self, name, mode="w"):
        self.name = name
        self.mode = mode
        self._fh = None

    @property
    def fh(self):
        if self._fh is None:
            self._fh = open(self.name, self.mode)
        return self._fh

    def flush(self):
        if self._fh is not None:
            return self.fh.flush()

    def close(self):
        if self._fh is not None:
            return self.fh.close()

    def __getattr__(self, a):
        return getattr(self.fh, a)


def cli(args=None, input_format="yaml", program_name="yq"):
    parser = get_parser(program_name, __doc__)
    argcomplete.autocomplete(parser)
    args, jq_args = parser.parse_known_args(args=args)
    null_input = False

    for i, arg in enumerate(jq_args):
        if arg.startswith("-") and not arg.startswith("--"):
            if "n" in arg:
                null_input = True
            if "i" in arg:
                args.in_place = True
            if "y" in arg:
                args.output_format = "yaml"
            elif "Y" in arg:
                args.output_format = "annotated_yaml"
            elif "x" in arg:
                args.output_format = "xml"
            jq_args[i] = arg.replace("i", "").replace("x", "").replace("y", "").replace("Y", "")
        if args.output_format != "json":
            jq_args[i] = jq_args[i].replace("C", "")
            if jq_args[i] == "-":
                jq_args[i] = None

    jq_args = [arg for arg in jq_args if arg is not None]

    for arg in jq_arg_spec:
        values = getattr(args, arg, None)
        delattr(args, arg)
        if values is not None:
            for value_group in values:
                jq_args.append(arg)
                jq_args.extend(value_group)
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
                args.input_streams.insert(0, open(os.devnull))
    delattr(args, "jq_filter")
    in_place = args.in_place
    delattr(args, "in_place")

    if sys.stdin.isatty() and not args.input_streams:
        parser.print_help()
        sys.exit(2)
    elif not args.input_streams:
        args.input_streams = [sys.stdin]

    yq_args = dict(input_format=input_format, program_name=program_name, jq_args=jq_args, **vars(args))
    if in_place:
        if args.output_format not in {"yaml", "annotated_yaml"}:
            sys.exit("{}: -i/--in-place can only be used with -y/-Y".format(program_name))
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
            yq(input_streams=[input_stream], output_stream=DeferredOutputStream(input_stream.name), **yq_args)
    else:
        yq(**yq_args)


def load_yaml_docs(in_stream, out_stream, jq, loader_class, max_expansion_factor, exit_func, prog):
    loader = loader_class(in_stream)

    last_loader_pos = 0
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
                    exit_func("{}: Error: detected unsafe YAML entity expansion".format(prog))
                out_stream.write(chunk)
            out_stream.write("\n")
            last_loader_pos = loader_pos
    finally:
        loader.dispose()


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
    explicit_start=False,
    explicit_end=False,
    expand_merge_keys=True,
    expand_aliases=True,
    max_expansion_factor=1024,
    yaml_output_grammar_version="1.1",
    jq_args=frozenset(),
    exit_func=None,
):
    if not input_streams:
        input_streams = [sys.stdin]
    if not output_stream:
        output_stream = sys.stdout
    if not exit_func:
        exit_func = sys.exit
    converting_output = True if output_format != "json" else False

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

    try:
        if converting_output:
            # TODO: enable true streaming in this branch (with asyncio, asyncproc, a multi-shot variant of
            # subprocess.Popen._communicate, etc.)
            # See https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
            use_annotations = True if output_format == "annotated_yaml" else False
            json_buffer = io.StringIO()
            for input_stream in input_streams:
                if input_format == "yaml":
                    loader_class = get_loader(
                        use_annotations=use_annotations,
                        expand_aliases=expand_aliases,
                        expand_merge_keys=expand_merge_keys,
                    )
                    load_yaml_docs(
                        in_stream=input_stream,
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
                        raise Exception("xml_item_depth is not supported with xq -x")

                    doc = xmltodict.parse(
                        input_stream.buffer if isinstance(input_stream, io.TextIOWrapper) else input_stream.read(),
                        disable_entities=True,
                        force_list=xml_force_list,
                    )
                    json.dump(doc, json_buffer, cls=JSONDateTimeEncoder)
                    json_buffer.write("\n")
                elif input_format == "toml":
                    import tomlkit

                    doc = tomlkit.load(input_stream)  # type: ignore
                    json.dump(doc, json_buffer, cls=JSONDateTimeEncoder)
                    json_buffer.write("\n")
                else:
                    raise Exception("Unknown input format")
            jq_out, jq_err = jq.communicate(json_buffer.getvalue())
            json_decoder = json.JSONDecoder()
            if output_format == "yaml" or output_format == "annotated_yaml":
                dumper_class = get_dumper(
                    use_annotations=use_annotations,
                    indentless=indentless_lists,
                    grammar_version=yaml_output_grammar_version,
                )
                yaml.dump_all(
                    decode_docs(jq_out, json_decoder),
                    stream=output_stream,
                    Dumper=dumper_class,
                    width=width,
                    allow_unicode=True,
                    default_flow_style=False,
                    explicit_start=explicit_start,
                    explicit_end=explicit_end,
                )
            elif output_format == "xml":
                import xmltodict

                for doc in decode_docs(jq_out, json_decoder):
                    if xml_root:
                        doc = {xml_root: doc}  # type: ignore
                    elif not isinstance(doc, dict):
                        msg = (
                            "{}: Error converting JSON to XML: cannot represent non-object types at top level. "
                            "Use --xml-root=name to envelope your output with a root element."
                        )
                        exit_func(msg.format(program_name))
                    full_document = True if xml_dtd else False
                    try:
                        xmltodict.unparse(
                            doc, output=output_stream, full_document=full_document, pretty=True, indent="  "
                        )
                    except ValueError as e:
                        if "Document must have exactly one root" in str(e):
                            raise Exception(str(e) + " Use --xml-root=name to envelope your output with a root element")
                        else:
                            raise
                    output_stream.write(b"\n" if sys.version_info < (3, 0) else "\n")
            elif output_format == "toml":
                import tomlkit

                for doc in decode_docs(jq_out, json_decoder):
                    if not isinstance(doc, dict):
                        msg = "{}: Error converting JSON to TOML: cannot represent non-object types at top level."
                        exit_func(msg.format(program_name))
                    tomlkit.dump(doc, output_stream)
        else:
            if input_format == "yaml":
                loader_class = get_loader(
                    use_annotations=False, expand_aliases=expand_aliases, expand_merge_keys=expand_merge_keys
                )
                for input_stream in input_streams:
                    load_yaml_docs(
                        in_stream=input_stream,
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
                    json.dump(entry, jq.stdin)  # type: ignore
                    jq.stdin.write("\n")  # type: ignore
                    return True

                for input_stream in input_streams:
                    doc = xmltodict.parse(
                        input_stream.buffer if isinstance(input_stream, io.TextIOWrapper) else input_stream.read(),
                        disable_entities=True,
                        force_list=xml_force_list,
                        item_depth=xml_item_depth,
                        item_callback=emit_entry,
                    )
                    if doc:
                        emit_entry(None, doc)
            elif input_format == "toml":
                import tomlkit

                for input_stream in input_streams:
                    json.dump(tomlkit.load(input_stream), jq.stdin, cls=JSONDateTimeEncoder)  # type: ignore
                    jq.stdin.write("\n")  # type: ignore
            else:
                raise Exception("Unknown input format")

            try:
                jq.stdin.close()  # type: ignore
            except Exception:
                pass
            jq.wait()
        for input_stream in input_streams:
            input_stream.close()
        exit_func(jq.returncode)
    except Exception as e:
        exit_func("{}: Error running jq: {}: {}.".format(program_name, type(e).__name__, e))
