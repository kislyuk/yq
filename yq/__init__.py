"""
yq: FIXME
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, subprocess, json
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("jq_args", nargs=argparse.REMAINDER)

def main(args=None):
    args = parser.parse_args(args=args)
    try:
        jq = subprocess.Popen(['jq'] + args.jq_args, stdin=subprocess.PIPE)
    except OSError as e:
        parser.exit("yq: Error while starting jq: {}: {}. Is jq installed and available on PATH?".format(type(e).__name__, e))
    try:
        json.dump(yaml.safe_load(sys.stdin), jq.stdin)
        jq.stdin.close()
        jq.wait()
        exit(jq.returncode)
    except Exception as e:
        parser.exit("yq: Error while running jq: {}: {}.".format(type(e).__name__, e))
