"""
yq: Command-line YAML processor - jq wrapper for YAML documents

yq transcodes YAML documents to JSON and passes them to jq.
See https://github.com/kislyuk/yq for more information.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, subprocess, json
from collections import OrderedDict
from datetime import datetime, date
import yaml
from .version import __version__

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

class JSONDateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date)):
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
        jq_output = jq_output[pos+1:]
        yield doc

OrderedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
OrderedDumper.add_representer(OrderedDict, represent_dict_order)

parser = Parser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("--yaml-output", "--yml-output", "-y", help="Transcode jq JSON output back into YAML and emit it",
                    action="store_true")
parser.add_argument("--width", "-w", type=int, help="When using --yaml-output, specify string wrap width")
parser.add_argument("--version", action="version", version="%(prog)s {version}".format(version=__version__))
parser.add_argument("jq_filter")
parser.add_argument("files", nargs="*", type=argparse.FileType())

def main(args=None):
    args, jq_args = parser.parse_known_args(args=args)
    if sys.stdin.isatty() and not args.files:
        return parser.print_help()

    try:
        # Note: universal_newlines is just a way to induce subprocess to make stdin a text buffer and encode it for us
        jq = subprocess.Popen(["jq"] + jq_args + [args.jq_filter],
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE if args.yaml_output else None,
                              universal_newlines=True)
    except OSError as e:
        msg = "yq: Error starting jq: {}: {}. Is jq installed and available on PATH?"
        parser.exit(msg.format(type(e).__name__, e))

    try:
        input_streams = args.files if args.files else [sys.stdin]
        if args.yaml_output:
            # TODO: enable true streaming in this branch (with asyncio, asyncproc, a multi-shot variant of
            # subprocess.Popen._communicate, etc.)
            # See https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
            input_docs = []
            for input_stream in input_streams:
                input_docs.extend(yaml.load_all(input_stream, Loader=OrderedLoader))
            input_payload = "\n".join(json.dumps(doc, cls=JSONDateTimeEncoder) for doc in input_docs)
            jq_out, jq_err = jq.communicate(input_payload)
            json_decoder = json.JSONDecoder(object_pairs_hook=OrderedDict)
            yaml.dump_all(decode_docs(jq_out, json_decoder), stream=sys.stdout, Dumper=OrderedDumper, width=args.width,
                          allow_unicode=True, default_flow_style=False)
        else:
            for input_stream in input_streams:
                for doc in yaml.load_all(input_stream, Loader=OrderedLoader):
                    json.dump(doc, jq.stdin, cls=JSONDateTimeEncoder)
                    jq.stdin.write("\n")
            jq.stdin.close()
            jq.wait()
        for input_stream in input_streams:
            input_stream.close()
        exit(jq.returncode)
    except Exception as e:
        parser.exit("yq: Error running jq: {}: {}.".format(type(e).__name__, e))
