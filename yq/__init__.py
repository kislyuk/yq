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
import locale
import os
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import threading
from collections import deque
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, time
from typing import List

import argcomplete
import yaml

from .dumper import get_dumper
from .loader import YAMLExpansionError, get_loader
from .parser import get_parser, jq_output_arg_spec
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


class JSONInputStreamWrapper:
    """Read the complete JSON records emitted by jq's compact output mode."""

    def __init__(self, stream, decoder):
        self.stream = stream
        self.decoder = decoder

    def __iter__(self):
        return self

    def has_next(self):
        return bool(self.stream.peek(1))

    def __next__(self):
        text = self.stream.readline().decode("utf-8")
        if not text:
            raise StopIteration
        if not text.endswith("\n"):
            # A terminated record distinguishes a complete number from a prefix
            # left behind when jq is interrupted during serialization.
            raise json.JSONDecodeError("Missing newline after jq output", text, len(text))
        return self.decoder.decode(text)


class YAMLInputStreamWrapper:
    """Replay only the prefix consumed while inspecting the leading marker."""

    def __init__(self, stream, flush=None):
        self.stream = stream
        self.flush = flush
        try:
            self.name = stream.name
        except AttributeError:
            self.name = "<file>"
        self.prefix: deque[str | bytes] = deque()
        self.offset = 0
        self.recording = False

    def read(self, size):
        if self.prefix and not self.recording:
            text = self.prefix[0][self.offset : self.offset + size]
            self.offset += len(text)
            if self.offset == len(self.prefix[0]):
                self.prefix.popleft()
                self.offset = 0
            return text
        # Deliver completed input to jq before a read can wait for more data.
        # Between reads, TextIOWrapper can batch writes from small documents.
        if self.flush is not None:
            self.flush()
        text = self.stream.read(size)
        if self.recording and text:
            self.prefix.append(text)
        return text

    def read_explicit_yaml_start(self, loader_class):
        # Use a separate parser because the C and Python composers consume start
        # events differently. Replay their bounded read-ahead even on nonseekable input.
        self.recording = True
        events = yaml.parse(self, Loader=loader_class)
        try:
            next(events)  # StreamStartEvent
            event = next(events)
            return isinstance(event, yaml.events.DocumentStartEvent) and event.explicit
        finally:
            events.close()
            self.recording = False


class InputBytesStreamWrapper(io.RawIOBase):
    """Wait for readable input while checking whether jq has already exited."""

    def __init__(self, stream, jq):
        self.source = stream
        self.stream = stream.buffer
        self.jq = jq
        self.name = stream.name
        self.wait_for_input = os.name == "posix" and not stat.S_ISREG(os.fstat(stream.fileno()).st_mode)

    def readable(self):
        return True

    def read(self, size=-1):
        if size == 0:
            return b""
        if size < 0:
            return self.readall()
        while True:
            # The main thread waits for jq before joining the input worker.
            if self.jq is not None and self.jq.returncode is not None:
                raise BrokenPipeError
            if not self.wait_for_input or select.select([self.stream], [], [], 0.1)[0]:
                # read1 returns available bytes without waiting to fill size.
                return self.stream.read1(size)

    read1 = read


def wrap_input_stream(stream, jq):
    return io.TextIOWrapper(
        InputBytesStreamWrapper(stream, jq), encoding=stream.encoding, errors=stream.errors, newline=""
    )


@contextmanager
def ignore_sigint():
    """Let subprocess cleanup finish even if Ctrl-C is pressed again."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, handler)


def silence_broken_stdout():
    # Prevent another BrokenPipeError when Python flushes stdout at shutdown.
    if isinstance(sys.stdout, io.TextIOWrapper):
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())


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
    # Also cover exceptions reported outside this boundary, including worker
    # failures and unraisable exceptions during interpreter shutdown.
    sys.tracebacklimit = 0
    try:
        _cli(args, input_format, program_name)
    except KeyboardInterrupt:
        silence_broken_stdout()
        sys.exit(130)
    except BrokenPipeError:
        silence_broken_stdout()
        sys.exit(141)
    except OSError as error:
        sys.exit(f"{program_name}: {error}")
    except SystemExit:
        raise
    except BaseException as error:
        sys.exit(f"{program_name}: {type(error).__name__}: {error}")


def _cli(args, input_format, program_name):
    parser = get_parser(program_name, __doc__)
    argcomplete.autocomplete(parser)
    args, jq_args = parser.parse_known_intermixed_args(args=args)
    null_input = False

    for arg, values in vars(args).pop("jq_options") or []:
        if arg in {"--null-input", "-n"}:
            null_input = True
        if args.output_format != "json" and arg in jq_output_arg_spec:
            continue
        jq_args.append(arg)
        jq_args.extend(values)
    with ExitStack() as input_stack:
        if args.jq_filter is not None:
            jq_filter_arg_loc = len(jq_args)
            if "--args" in jq_args:
                jq_filter_arg_loc = jq_args.index("--args") + 1
            elif "--jsonargs" in jq_args:
                jq_filter_arg_loc = jq_args.index("--jsonargs") + 1
            jq_args.insert(jq_filter_arg_loc, args.jq_filter)
            if null_input and not args.in_place:
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
            if any(not isinstance(stream, str) or stream == "-" for stream in input_streams):
                msg = "{}: -i/--in-place can only be used with filename arguments, not on standard input"
                sys.exit(msg.format(program_name))

            def exit_handler(arg=None):
                if arg:
                    sys.exit(arg)

            yq_args["exit_func"] = exit_handler

            for path in input_streams:
                edit_in_place(path, yq_args)
        else:
            yq(**yq_args)


def edit_in_place(path, yq_args):
    # Keep one descriptor for reading and writing, so replacing the
    # path during processing cannot redirect the write to another file.
    with open(path, "r+b", buffering=0) as target:
        if not stat.S_ISREG(os.fstat(target.fileno()).st_mode):
            raise OSError(f"--in-place requires a regular file: {path}")
        encoding = locale.getpreferredencoding(do_setlocale=False)
        source = io.StringIO(target.read().decode(encoding))
        source.name = path
        with io.StringIO() as output:
            yq(input_streams=[source], output_stream=output, **yq_args)
            replacement = output.getvalue().encode(encoding)
        try:
            target.seek(0)
            write_all(target, replacement)
            target.truncate()
            target.flush()
            os.fsync(target.fileno())
        except OSError as error:
            raise OSError(f"writing {path} failed ({error}); the file may be incomplete") from error


def write_all(stream, data):
    remaining = memoryview(data)
    while remaining:
        size = stream.write(remaining[: 64 * 1024])
        if not size:
            raise OSError("write made no progress")
        remaining = remaining[size:]


def load_yaml_docs(in_stream, out_stream, jq, loader_class, max_expansion_factor, exit_func, prog, on_document=None):
    loader = loader_class(in_stream)

    last_loader_pos = 0
    doc_count = 0
    try:
        while loader.check_node():
            if on_document is not None:
                on_document()
            node = loader.get_node()
            loader_pos = node.end_mark.index
            doc_len = loader_pos - last_loader_pos
            loader.max_merge_expansion = doc_len * max_expansion_factor
            loader.merge_expansion = 0
            doc = loader.construct_document(node)
            del node
            doc_bytes_written = 0
            for chunk in JSONDateTimeEncoder().iterencode(doc):
                doc_bytes_written += len(chunk)
                if doc_bytes_written > doc_len * max_expansion_factor:
                    raise YAMLExpansionError
                out_stream.write(chunk)
            out_stream.write("\n")
            # Assignment on the next iteration would keep this document alive
            # throughout construction of its successor.
            del doc, chunk
            last_loader_pos = loader_pos
            doc_count += 1
    except YAMLExpansionError:
        if jq:
            jq.kill()
        exit_func(f"{prog}: Error: detected unsafe YAML entity expansion")
    finally:
        loader.dispose()
    return doc_count


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

    use_annotations = output_format == "annotated_yaml"
    input_doc_count = 0
    yaml_boundary = ""
    frontmatter_body = None
    input_done = threading.Event()
    input_stack = ExitStack()
    input_name = "<stdin>"

    def read_inputs():
        nonlocal input_name
        previous_source = None
        for source in input_streams:
            if isinstance(source, str):
                input_name = source
                if source == "-":
                    source = sys.stdin
                else:
                    # Opening a later FIFO must not block earlier documents,
                    # nor keep yq alive after jq has failed to compile.
                    flags = os.O_RDONLY
                    if os.name == "posix":
                        flags |= os.O_NONBLOCK
                    fd = os.open(source, flags)
                    source = input_stack.enter_context(
                        open(fd, encoding=locale.getpreferredencoding(do_setlocale=False), newline="")  # noqa: SIM115
                    )
                    # Overlap handles until the next open completes. Closing
                    # the last handle first is costly on some filesystems.
                    if previous_source is not None:
                        previous_source.close()
                    stream = input_stack.enter_context(wrap_input_stream(source, jq))
                    assert isinstance(stream.buffer, InputBytesStreamWrapper)
                    stream.buffer.name = input_name
                    yield stream
                    if not yaml_frontmatter:
                        previous_source = source
                    continue
            try:
                input_name = source.name
            except AttributeError:
                input_name = "<file>"
            # CLI standard input has not been read yet. Caller-supplied text
            # streams may already have decoded read-ahead; leave that intact.
            yield (
                input_stack.enter_context(wrap_input_stream(source, jq))
                if source is sys.stdin and isinstance(source, io.TextIOWrapper)
                else source
            )
        if previous_source is not None:
            previous_source.close()

    def note_yaml_document():
        nonlocal input_doc_count
        input_doc_count += 1

    def write_input():
        nonlocal yaml_boundary, explicit_start, frontmatter_body
        assert jq.stdin is not None
        if input_format == "yaml":
            loader_class = get_loader(
                use_annotations=use_annotations, expand_aliases=expand_aliases, expand_merge_keys=expand_merge_keys
            )
            for input_stream in read_inputs():
                # PyYAML decodes byte streams itself. Passing the native text
                # reader here would wait to fill its read(n) on an open FIFO.
                yaml_stream = input_stream
                if isinstance(input_stream, io.TextIOWrapper) and isinstance(
                    input_stream.buffer, InputBytesStreamWrapper
                ):
                    yaml_stream = input_stream.buffer
                if yaml_frontmatter:
                    header, yaml_boundary = read_yaml_frontmatter(input_stream)
                    yaml_stream = io.StringIO(header)
                    yaml_stream.name = input_name
                    frontmatter_body = input_stream
                    del header
                yaml_stream = YAMLInputStreamWrapper(yaml_stream, flush=jq.stdin.flush)
                if output_format in {"yaml", "annotated_yaml"} and not input_doc_count:
                    explicit_start = yaml_stream.read_explicit_yaml_start(loader_class) or explicit_start
                load_yaml_docs(
                    in_stream=yaml_stream,
                    out_stream=jq.stdin,
                    jq=jq,
                    loader_class=loader_class,
                    max_expansion_factor=max_expansion_factor,
                    exit_func=exit_func,
                    prog=program_name,
                    on_document=note_yaml_document,
                )
                jq.stdin.flush()
                del yaml_stream
        elif input_format == "xml":
            import xmltodict

            if converting_output and xml_item_depth != 0:
                raise ValueError("xml_item_depth is not supported with xq -x")

            def emit_entry(path, entry):
                assert jq.stdin is not None
                json.dump(entry, jq.stdin, cls=JSONDateTimeEncoder)
                jq.stdin.write("\n")
                jq.stdin.flush()
                return True

            for input_stream in read_inputs():
                xml_doc = xmltodict.parse(
                    input_stream.buffer if isinstance(input_stream, io.TextIOWrapper) else input_stream.read(),
                    disable_entities=True,
                    force_list=xml_force_list,
                    item_depth=xml_item_depth,
                    item_callback=emit_entry,
                )
                if xml_doc or converting_output:
                    emit_entry(None, xml_doc)
                del xml_doc
        elif input_format == "toml":
            toml_loader = get_toml_loader()
            for input_stream in read_inputs():
                if converting_output:
                    import tomlkit

                    toml_doc = tomlkit.load(input_stream)
                    json.dump(
                        tomlkit_to_json(toml_doc, use_annotations=output_format == "annotated_toml"),
                        jq.stdin,
                        cls=JSONDateTimeEncoder,
                    )
                else:
                    toml_doc = toml_loader(input_stream.read())
                    json.dump(toml_doc, jq.stdin, cls=JSONDateTimeEncoder)
                jq.stdin.write("\n")
                jq.stdin.flush()
                del toml_doc
        else:
            raise ValueError("Unknown input format")

    def write_yaml_output(docs):
        dumper_class = get_dumper(
            use_annotations=use_annotations, indentless=indentless_lists, grammar_version=yaml_output_grammar_version
        )
        pending_end = False
        doc_count = 0
        for doc in docs:
            if doc_count == 0:
                if yaml_frontmatter:
                    if docs.has_next():
                        raise ValueError("--yaml-frontmatter requires the jq filter to produce exactly one document")
                    if jq.wait():
                        return
                    input_done.wait()
                if explicit_start or yaml_boundary:
                    output_stream.write("---\n")
            else:
                output_stream.write("---\n")
            dumper = dumper_class(
                stream=output_stream,
                width=sys.maxsize if width == 0 else width,
                allow_unicode=True,
                default_flow_style=False,
                explicit_end=explicit_end and not (yaml_frontmatter and yaml_boundary.startswith("...")),
            )
            try:
                dumper.open()
                dumper.represent(doc)
                # Only StreamEnd can add an implicit scalar end marker. Defer
                # that marker; the next '---' or frontmatter fence can end it.
                pending_end = dumper.open_ended
                dumper.open_ended = False
                dumper.close()
            finally:
                dumper.dispose()
            del doc
            output_stream.flush()
            doc_count += 1

        if yaml_frontmatter and not doc_count:
            jq.wait()
            input_done.wait()
            if jq.returncode:
                return
            raise ValueError("--yaml-frontmatter requires the jq filter to produce exactly one document")
        # The original frontmatter fence terminates even a scalar document.
        if pending_end and not yaml_boundary:
            output_stream.write("...\n")
        if yaml_boundary:
            output_stream.write(yaml_boundary)
        output_stream.flush()

    def write_output():
        assert isinstance(jq.stdout, io.TextIOWrapper)
        docs = JSONInputStreamWrapper(jq.stdout.buffer, json.JSONDecoder())
        if output_format in {"yaml", "annotated_yaml"}:
            write_yaml_output(docs)
        elif output_format == "xml":
            import xmltodict

            for doc in docs:
                if xml_root:
                    doc = {xml_root: doc}
                elif not isinstance(doc, dict):
                    msg = (
                        "{}: Error converting JSON to XML: cannot represent non-object types at top level. "
                        "Use --xml-root=name to envelope your output with a root element."
                    )
                    exit_func(msg.format(program_name))
                try:
                    xmltodict.unparse(
                        doc,
                        output=output_stream,
                        full_document=bool(xml_dtd),
                        pretty=True,
                        indent="  ",
                        short_empty_elements=xml_short_empty_elements,
                    )
                except ValueError as e:
                    if "Document must have exactly one root" in str(e):
                        raise ValueError(
                            str(e) + " Use --xml-root=name to envelope your output with a root element"
                        ) from e
                    raise
                output_stream.write("\n")
                output_stream.flush()
                del doc
        elif output_format in {"toml", "annotated_toml"}:
            import tomlkit

            for doc in docs:
                if not isinstance(doc, dict):
                    msg = "{}: Error converting JSON to TOML: cannot represent non-object types at top level."
                    exit_func(msg.format(program_name))
                if output_format == "annotated_toml":
                    doc = tomlkit_from_json(doc)
                tomlkit.dump(doc, output_stream)
                output_stream.flush()
                del doc
        else:
            raise ValueError("Unknown output format")

    input_errors: list[BaseException] = []

    def produce_input():
        try:
            write_input()
        except BrokenPipeError:
            # first(inputs), halt and compile errors can stop input early.
            pass
        except BaseException as error:
            # EOF lets jq finish already accepted documents. Killing it here
            # could truncate output from an earlier valid document.
            input_errors.append(error)
        finally:
            assert jq.stdin is not None
            try:
                jq.stdin.close()
            except BrokenPipeError:
                pass
            except BaseException as error:
                input_errors.append(error)
            finally:
                input_done.set()

    try:
        # Unbuffered jq output lets readers make progress with small documents.
        # Keep inherited descriptors for command substitution (e.g. --slurpfile).
        jq = subprocess.Popen(
            ["jq"]
            + (["--compact-output", "--monochrome-output", "--unbuffered"] if converting_output else [])
            + list(jq_args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE if converting_output else None,
            close_fds=False,
            universal_newlines=True,
        )
    except OSError as e:
        msg = "{}: Error starting jq: {}: {}. Is jq installed and available on PATH?"
        exit_func(msg.format(program_name, type(e).__name__, e))
        return

    # Output stays on the main thread so Ctrl-C also interrupts a blocked
    # stdout write. Input reads and jq stdin writes stop when jq is killed.
    input_thread = threading.Thread(target=produce_input)
    output_error = None
    stage = f"converting jq output to {output_format.upper()}"
    try:
        try:
            input_thread.start()
            try:
                if converting_output:
                    write_output()
                jq.wait()
            except (Exception, SystemExit) as error:
                output_error = error
        finally:
            with ignore_sigint():
                if jq.poll() is None:
                    jq.kill()
                jq.wait()
                if input_thread.ident is not None:
                    input_thread.join()
                elif jq.stdin is not None:
                    jq.stdin.close()
                if jq.stdout is not None:
                    jq.stdout.close()
        if input_errors:
            stage = f"reading {input_format.upper()} input ({input_name})"
            raise input_errors[0]
        if output_error is not None:
            raise output_error
        if yaml_boundary and converting_output and not jq.returncode:
            stage = "copying the frontmatter body"
            assert frontmatter_body is not None
            if isinstance(frontmatter_body, io.TextIOWrapper) and isinstance(
                frontmatter_body.buffer, InputBytesStreamWrapper
            ):
                frontmatter_body.buffer.jq = None
            shutil.copyfileobj(frontmatter_body, output_stream, length=64 * 1024)
            output_stream.flush()
        exit_func(128 - jq.returncode if jq.returncode < 0 else jq.returncode)
    except KeyboardInterrupt:
        if output_stream is sys.stdout:
            silence_broken_stdout()
        exit_func(130)
    except BrokenPipeError:
        if output_stream is sys.stdout:
            silence_broken_stdout()
        exit_func(141)
    except json.JSONDecodeError as error:
        exit_func(f"{program_name}: jq produced invalid JSON for {output_format.upper()} output: {error}.")
    except Exception as e:
        exit_func(f"{program_name}: Error {stage}: {type(e).__name__}: {e}.")
    finally:
        input_stack.close()
        for input_stream in input_streams:
            if not isinstance(input_stream, str):
                input_stream.close()
