import argparse
import subprocess
import sys
from typing import Union

try:
    from .version import version as __version__
except ImportError:
    __version__ = "0.0.0"

# jq arguments that consume positionals must be listed here to avoid our parser mistaking them for our positionals
jq_arg_spec = {
    "--indent": 1,
    "-f": 1,
    "--from-file": 1,
    "-L": 1,
    "--arg": 2,
    "--argjson": 2,
    "--slurpfile": 2,
    "--argfile": 2,
    "--rawfile": 2,
    "--args": argparse.REMAINDER,
    "--jsonargs": argparse.REMAINDER,
}


class Parser(argparse.ArgumentParser):
    def print_help(self):
        yq_help = argparse.ArgumentParser.format_help(self).splitlines()
        print("\n".join(["usage: {} [options] <jq filter> [input file...]".format(self.prog)] + yq_help[2:] + [""]))
        sys.stdout.flush()
        try:
            subprocess.check_call(["jq", "--help"])
        except Exception:
            pass


def get_parser(program_name, description):
    # By default suppress these help strings and only enable them in the specific programs.
    yaml_output_help, yaml_roundtrip_help, width_help, indentless_help, grammar_help = [argparse.SUPPRESS] * 5
    xml_output_help, xml_item_depth_help, xml_dtd_help, xml_root_help, xml_force_list_help = [argparse.SUPPRESS] * 5
    toml_output_help = argparse.SUPPRESS

    if program_name == "yq":
        current_language = "YAML"
        yaml_output_help = "Transcode jq JSON output back into YAML and emit it"
        yaml_roundtrip_help = (
            "Transcode jq JSON output back into YAML and emit it. "
            "Preserve YAML tags and styles by representing them as extra items "
            "in their enclosing mappings and sequences while in JSON. This option "
            "is incompatible with jq filters that do not expect these extra items."
        )
        width_help = "When using --yaml-output, specify string wrap width"
        indentless_help = "When using --yaml-output, indent block style lists (sequences) with 0 spaces instead of 2"
        grammar_help = (
            "When using --yaml-output, specify output grammar (the default is 1.1 and will be changed "
            "to 1.2 in a future version). Setting this to 1.2 will cause strings like 'on' and 'no' to be "
            "emitted unquoted."
        )
    elif program_name == "xq":
        current_language = "XML"
        xml_output_help = "Transcode jq JSON output back into XML and emit it"
        xml_item_depth_help = "Specify depth of items to emit (default 0; use a positive integer to stream large docs)"
        xml_dtd_help = "Preserve XML Document Type Definition (disables streaming of multiple docs)"
        xml_root_help = "When transcoding back to XML, envelope the output in an element with this name"
        xml_force_list_help = "Emit a list for elements with this name even if they occur only once (option can repeat)"
    elif program_name == "tomlq":
        current_language = "TOML"
        toml_output_help = "Transcode jq JSON output back into TOML and emit it"
    else:
        raise Exception("Unknown program name")

    description = description.replace("yq", program_name).replace("YAML", current_language)
    parser_args = dict(prog=program_name, description=description, formatter_class=argparse.RawTextHelpFormatter)
    if sys.version_info >= (3, 5):
        parser_args.update(allow_abbrev=False)  # required to disambiguate options listed in jq_arg_spec
    parser = Parser(**parser_args)
    parser.add_argument("--output-format", default="json", help=argparse.SUPPRESS)
    parser.add_argument(
        "--yaml-output",
        "--yml-output",
        "-y",
        dest="output_format",
        action="store_const",
        const="yaml",
        help=yaml_output_help,
    )
    parser.add_argument(
        "--yaml-roundtrip",
        "--yml-roundtrip",
        "-Y",
        dest="output_format",
        action="store_const",
        const="annotated_yaml",
        help=yaml_roundtrip_help,
    )
    parser.add_argument(
        "--yaml-output-grammar-version", "--yml-out-ver", choices=["1.1", "1.2"], default="1.1", help=grammar_help
    )
    parser.add_argument("--width", "-w", type=int, help=width_help)
    parser.add_argument("--indentless-lists", "--indentless", action="store_true", help=indentless_help)
    parser.add_argument("--explicit-start", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--explicit-end", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-expand-aliases", action="store_false", dest="expand_aliases", help=argparse.SUPPRESS)
    parser.add_argument("--max-expansion-factor", type=int, default=1024, help=argparse.SUPPRESS)
    parser.add_argument(
        "--xml-output", "-x", dest="output_format", action="store_const", const="xml", help=xml_output_help
    )
    parser.add_argument("--xml-item-depth", type=int, default=0, help=xml_item_depth_help)
    parser.add_argument("--xml-dtd", action="store_true", help=xml_dtd_help)
    parser.add_argument("--xml-root", help=xml_root_help)
    parser.add_argument("--xml-force-list", action="append", help=xml_force_list_help)
    parser.add_argument(
        "--toml-output", "-t", dest="output_format", action="store_const", const="toml", help=toml_output_help
    )
    parser.add_argument("--in-place", "-i", action="store_true", help="Edit files in place (no backup - use caution)")
    parser.add_argument("--version", action="version", version="%(prog)s {version}".format(version=__version__))

    for arg in jq_arg_spec:
        nargs: Union[int, str] = jq_arg_spec[arg]  # type: ignore
        parser.add_argument(arg, nargs=nargs, dest=arg, action="append", help=argparse.SUPPRESS)

    parser.add_argument("jq_filter", nargs="?")
    parser.add_argument("input_streams", nargs="*", type=argparse.FileType(), metavar="files", default=[])
    return parser
