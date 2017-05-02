"""
yq: Command-line YAML processor - jq wrapper for YAML documents

yq transcodes YAML documents to JSON and passes them to jq.
See https://github.com/kislyuk/yq for more information.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, subprocess, json
from collections import OrderedDict
import yaml

class Parser(argparse.ArgumentParser):
    def print_help(self):
        yq_help = argparse.ArgumentParser.format_help(self).splitlines()
        print("\n".join(["usage: yq [options] <jq filter> [YAML file...]"] + yq_help[1:] + [""]))
        try:
            subprocess.check_call(["jq", "--help"])
        except:
            pass

class OrderedLoader(yaml.SafeLoader):
    pass

class OrderedDumper(yaml.SafeDumper):
    pass

def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))

def represent_dict_order(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())

OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
OrderedDumper.add_representer(OrderedDict, represent_dict_order)

parser = Parser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("--yaml-output", "--yml-output", "-y", help="Transcode jq JSON output back into YAML and emit it",
                    action="store_true")
parser.add_argument("--width", "-w", type=int, help="When using --yaml-output, specify string wrap width")
parser.add_argument("jq_filter")
parser.add_argument("file", nargs="*", type=argparse.FileType())

def main(args=None):
    args, jq_args = parser.parse_known_args(args=args)
    if sys.stdin.isatty() and not args.file:
        return parser.print_help()
    try:
        # Note: universal_newlines is just a way to induce subprocess to make stdin a text buffer and encode it for us
        jq = subprocess.Popen(["jq"] + jq_args + [args.jq_filter],
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE if args.yaml_output else None,
                              universal_newlines=True)
    except OSError as e:
        msg = "yq: Error while starting jq: {}: {}. Is jq installed and available on PATH?"
        parser.exit(msg.format(type(e).__name__, e))
    try:
        input_stream = args.file[0] if args.file else sys.stdin
        if args.yaml_output:
            out, err = jq.communicate(json.dumps(yaml.load(input_stream, Loader=OrderedLoader)))
            out = json.loads(out, object_pairs_hook=OrderedDict)
            yaml.dump(out, stream=sys.stdout, Dumper=OrderedDumper, width=args.width,
                      allow_unicode=True, default_flow_style=False)
        else:
            json.dump(yaml.load(input_stream, Loader=OrderedLoader), jq.stdin)
            jq.stdin.close()
            jq.wait()
        exit(jq.returncode)
    except Exception as e:
        parser.exit("yq: Error while running jq: {}: {}.".format(type(e).__name__, e))
