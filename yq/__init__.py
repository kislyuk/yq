"""
yq: Command-line YAML processor - jq wrapper for YAML documents

yq transcodes YAML documents to JSON and passes them to jq.
See https://github.com/kislyuk/yq for more information.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, subprocess, json
import yaml

class Parser(argparse.ArgumentParser):
    def print_help(self):
        yq_help = argparse.ArgumentParser.format_help(self).splitlines()
        print("\n".join(["usage: yq [options] <jq filter> [YAML file...]"] + yq_help[1:] + [""]))
        try:
            subprocess.check_call(["jq", "--help"])
        except:
            pass

parser = Parser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("jq_args", nargs=argparse.REMAINDER)

def main(args=None):
    args = parser.parse_args(args=args)
    if sys.stdin.isatty():
        return parser.print_help()
    try:
        # Note: universal_newlines is just a way to induce subprocess to make stdin a text buffer and encode it for us
        jq = subprocess.Popen(['jq'] + args.jq_args, stdin=subprocess.PIPE, universal_newlines=True)
    except OSError as e:
        parser.exit("yq: Error while starting jq: {}: {}. Is jq installed and available on PATH?".format(type(e).__name__, e))
    try:
        json.dump(yaml.safe_load(sys.stdin), jq.stdin)
        jq.stdin.close()
        jq.wait()
        exit(jq.returncode)
    except Exception as e:
        parser.exit("yq: Error while running jq: {}: {}.".format(type(e).__name__, e))
