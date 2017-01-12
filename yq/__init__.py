"""
yq: FIXME
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, logging, json
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("jq_args", nargs=argparse.REMAINDER)

def main(args=None):
    raise NotImplementedError()
