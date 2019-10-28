"""
yq: Command-line YAML processor - jq wrapper for YAML documents

yq transcodes YAML documents to JSON and passes them to jq.
See https://github.com/kislyuk/yq for more information.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import sys, argparse, subprocess, json
from collections import OrderedDict
from datetime import datetime, date, time

import yaml

from .version import __version__

class Parser(argparse.ArgumentParser):
    def print_help(self):
        yq_help = argparse.ArgumentParser.format_help(self).splitlines()
        print("\n".join(["usage: yq [options] <jq filter> [YAML file...]"] + yq_help[1:] + [""]))
        try:
            subprocess.check_call(["jq", "--help"])
        except Exception:
            pass

class OrderedLoader(yaml.SafeLoader):
    pass

class OrderedIndentlessDumper(yaml.SafeDumper):
    pass

class OrderedDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(OrderedDumper, self).increase_indent(flow, False)

class JSONDateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))

def represent_dict_order(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())

def decode_docs(jq_output, json_decoder):
    while jq_output:
        doc, pos = json_decoder.raw_decode(jq_output)
        jq_output = jq_output[pos + 1:]
        yield doc

def parse_unknown_tags(loader, tag_suffix, node):
    if isinstance(node, yaml.nodes.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.nodes.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.nodes.MappingNode):
        return construct_mapping(loader, node)

OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
OrderedLoader.add_multi_constructor('', parse_unknown_tags)

for dumper in OrderedIndentlessDumper, OrderedDumper:
    dumper.add_representer(OrderedDict, represent_dict_order)

# jq arguments that consume positionals must be listed here to avoid our parser mistaking them for our positionals
jq_arg_spec = {"--indent": 1, "-f": 1, "--from-file": 1, "-L": 1, "--arg": 2, "--argjson": 2, "--slurpfile": 2,
               "--argfile": 2, "--rawfile": 2, "--args": argparse.REMAINDER, "--jsonargs": argparse.REMAINDER}

# Detection for Python 2
USING_PYTHON2 = True if sys.version_info < (3, 0) else False

def get_parser(program_name):
    # By default suppress these help strings and only enable them in the specific programs.
    yaml_output_help, width_help, indentless_help = argparse.SUPPRESS, argparse.SUPPRESS, argparse.SUPPRESS
    xml_output_help, xml_dtd_help, xml_root_help = argparse.SUPPRESS, argparse.SUPPRESS, argparse.SUPPRESS
    toml_output_help = argparse.SUPPRESS

    if program_name == "yq":
        current_language = "YAML"
        yaml_output_help = "Transcode jq JSON output back into YAML and emit it"
        width_help = "When using --yaml-output, specify string wrap width"
        indentless_help = 'When using --yaml-output, indent block style lists (sequences) with 0 spaces instead of 2'
    elif program_name == "xq":
        current_language = "XML"
        xml_output_help = "Transcode jq JSON output back into XML and emit it"
        xml_dtd_help = "Preserve XML Document Type Definition (disables streaming of multiple docs)"
        xml_root_help = "When transcoding back to XML, envelope the output in an element with this name"
    elif program_name == "tq":
        current_language = "TOML"
        toml_output_help = "Transcode jq JSON output back into TOML and emit it"
    else:
        raise Exception("Unknown program name")

    description = __doc__.replace("yq", program_name).replace("YAML", current_language)
    parser_args = dict(prog=program_name, description=description, formatter_class=argparse.RawTextHelpFormatter)
    if sys.version_info >= (3, 5):
        parser_args.update(allow_abbrev=False)  # required to disambiguate options listed in jq_arg_spec
    parser = Parser(**parser_args)
    parser.add_argument("--output-format", default="json", help=argparse.SUPPRESS)
    parser.add_argument("--yaml-output", "--yml-output", "-y", dest="output_format", action="store_const", const="yaml",
                        help=yaml_output_help)
    parser.add_argument("--width", "-w", type=int, help=width_help)
    parser.add_argument("--indentless-lists", "--indentless", action="store_true", help=indentless_help)
    parser.add_argument("--xml-output", "-x", dest="output_format", action="store_const", const="xml",
                        help=xml_output_help)
    parser.add_argument("--xml-dtd", action="store_true", help=xml_dtd_help)
    parser.add_argument("--xml-root", help=xml_root_help)
    parser.add_argument("--toml-output", "-t", dest="output_format", action="store_const", const="toml",
                        help=toml_output_help)
    parser.add_argument("--version", action="version", version="%(prog)s {version}".format(version=__version__))

    for arg in jq_arg_spec:
        parser.add_argument(arg, nargs=jq_arg_spec[arg], dest=arg, action="append", help=argparse.SUPPRESS)

    parser.add_argument("jq_filter")
    parser.add_argument("input_streams", nargs="*", type=argparse.FileType(), metavar="files", default=[sys.stdin])
    return parser

def xq_cli():
    cli(input_format="xml", program_name="xq")

def tq_cli():
    cli(input_format="toml", program_name="tq")

def cli(args=None, input_format="yaml", program_name="yq"):
    parser = get_parser(program_name)
    args, jq_args = parser.parse_known_args(args=args)

    for i, arg in enumerate(jq_args):
        if arg.startswith("-") and not arg.startswith("--"):
            if "y" in arg:
                args.output_format = "yaml"
            elif "x" in arg:
                args.output_format = "xml"
            jq_args[i] = arg.replace("x", "").replace("y", "")
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

    if "--from-file" in jq_args or "-f" in jq_args:
        args.input_streams.insert(0, argparse.FileType()(args.jq_filter))
    else:
        jq_filter_arg_loc = len(jq_args)
        if "--args" in jq_args:
            jq_filter_arg_loc = jq_args.index('--args') + 1
        elif "--jsonargs" in jq_args:
            jq_filter_arg_loc = jq_args.index('--jsonargs') + 1
        jq_args.insert(jq_filter_arg_loc, args.jq_filter)
    delattr(args, "jq_filter")

    if sys.stdin.isatty() and not args.input_streams:
        return parser.print_help()

    yq(input_format=input_format, program_name=program_name, jq_args=jq_args, **vars(args))

def yq(input_streams=None, output_stream=None, input_format="yaml", output_format="json",
       program_name="yq", width=None, indentless_lists=False, xml_root=None, xml_dtd=False, jq_args=frozenset(),
       exit_func=None):
    if not input_streams:
        input_streams = [sys.stdin]
    if not output_stream:
        output_stream = sys.stdout
    if not exit_func:
        exit_func = sys.exit
    converting_output = True if output_format != "json" else False

    try:
        # Note: universal_newlines is just a way to induce subprocess to make stdin a text buffer and encode it for us
        jq = subprocess.Popen(["jq"] + list(jq_args),
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE if converting_output else None,
                              universal_newlines=True)
    except OSError as e:
        msg = "{}: Error starting jq: {}: {}. Is jq installed and available on PATH?"
        exit_func(msg.format(program_name, type(e).__name__, e))

    try:
        if converting_output:
            # TODO: enable true streaming in this branch (with asyncio, asyncproc, a multi-shot variant of
            # subprocess.Popen._communicate, etc.)
            # See https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
            input_docs = []
            for input_stream in input_streams:
                if input_format == "yaml":
                    input_docs.extend(yaml.load_all(input_stream, Loader=OrderedLoader))
                elif input_format == "xml":
                    import xmltodict
                    input_docs.append(xmltodict.parse(input_stream.read(), disable_entities=True))
                elif input_format == "toml":
                    import toml
                    input_docs.append(toml.load(input_stream))
                else:
                    raise Exception("Unknown input format")
            input_payload = "\n".join(json.dumps(doc, cls=JSONDateTimeEncoder) for doc in input_docs)
            jq_out, jq_err = jq.communicate(input_payload)
            json_decoder = json.JSONDecoder(object_pairs_hook=OrderedDict)
            if output_format == "yaml":
                dumper_class = OrderedIndentlessDumper if indentless_lists else OrderedDumper
                yaml.dump_all(decode_docs(jq_out, json_decoder), stream=output_stream, Dumper=dumper_class,
                              width=width, allow_unicode=True, default_flow_style=False)
            elif output_format == "xml":
                import xmltodict
                for doc in decode_docs(jq_out, json_decoder):
                    if xml_root:
                        doc = {xml_root: doc}
                    elif not isinstance(doc, OrderedDict):
                        msg = ("{}: Error converting JSON to XML: cannot represent non-object types at top level. "
                               "Use --xml-root=name to envelope your output with a root element.")
                        exit_func(msg.format(program_name))
                    full_document = True if xml_dtd else False
                    try:
                        xmltodict.unparse(doc, output=output_stream, full_document=full_document, pretty=True,
                                          indent="  ")
                    except ValueError as e:
                        if "Document must have exactly one root" in str(e):
                            raise Exception(str(e) + " Use --xml-root=name to envelope your output with a root element")
                        else:
                            raise
                    output_stream.write(b"\n" if sys.version_info < (3, 0) else "\n")
            elif output_format == "toml":
                import toml
                for doc in decode_docs(jq_out, json_decoder):
                    if not isinstance(doc, OrderedDict):
                        msg = "{}: Error converting JSON to TOML: cannot represent non-object types at top level."
                        exit_func(msg.format(program_name))

                    if USING_PYTHON2:
                        # For Python 2, dump the string and encode it into bytes.
                        output = toml.dumps(doc)
                        output_stream.write(output.encode("utf-8"))
                    else:
                        # For Python 3, write the unicode to the buffer directly.
                        toml.dump(doc, output_stream)
        else:
            if input_format == "yaml":
                for input_stream in input_streams:
                    for doc in yaml.load_all(input_stream, Loader=OrderedLoader):
                        json.dump(doc, jq.stdin, cls=JSONDateTimeEncoder)
                        jq.stdin.write("\n")
            elif input_format == "xml":
                import xmltodict
                for input_stream in input_streams:
                    json.dump(xmltodict.parse(input_stream.read(), disable_entities=True), jq.stdin)
                    jq.stdin.write("\n")
            elif input_format == "toml":
                import toml
                for input_stream in input_streams:
                    json.dump(toml.load(input_stream), jq.stdin)
                    jq.stdin.write("\n")
            else:
                raise Exception("Unknown input format")

            jq.stdin.close()
            jq.wait()
        for input_stream in input_streams:
            input_stream.close()
        exit_func(jq.returncode)
    except Exception as e:
        exit_func("{}: Error running jq: {}: {}.".format(program_name, type(e).__name__, e))
