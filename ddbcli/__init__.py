"""
ddbcli: DynamoDB Command Line Interface
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, argparse, logging, shutil, json, datetime, traceback, errno
import boto3
from botocore.exceptions import NoRegionError
from tweak import Config

logger = logging.getLogger(__name__)
config = Config("ddbcli")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--log-level", type=logger.setLevel,
                    help=str([logging.getLevelName(i) for i in range(0, 60, 10)]),
                    default=logging.WARN)
subparsers = parser.add_subparsers()

def register_parser(function, **add_parser_args):
    subparser = subparsers.add_parser(function.__name__, **add_parser_args)
    subparser.add_argument("table")
    subparser.set_defaults(entry_point=function)
    if subparser.description is None:
        subparser.description = add_parser_args.get("help", function.__doc__)
    return subparser

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    if "DYNAMODB_TABLE" in os.environ:
        args.insert(1, os.environ["DYNAMODB_TABLE"])
    parsed_args = parser.parse_args(args=args)
    try:
        result = parsed_args.entry_point(parsed_args)
    except Exception as e:
        if isinstance(e, NoRegionError):
            msg = "The AWS CLI is not configured."
            msg += " Please configure it using instructions at"
            msg += " http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html"
            exit(msg)
        elif logger.level < logging.ERROR:
            raise
        else:
            err_msg = traceback.format_exc()
            try:
                err_log_filename = os.path.join(config.user_config_dir, "error.log")
                with open(err_log_filename, "ab") as fh:
                    print(datetime.datetime.now().isoformat(), file=fh)
                    print(err_msg, file=fh)
                exit("{}: {}. See {} for error details.".format(e.__class__.__name__, e, err_log_filename))
            except Exception:
                print(err_msg, file=sys.stderr)
                exit(os.EX_SOFTWARE)
    if isinstance(result, SystemExit):
        raise result
    elif result is not None:
        if isinstance(result, dict) and "ResponseMetadata" in result:
            del result["ResponseMetadata"]
        print(json.dumps(result, indent=2, default=lambda x: str(x)))

def get_key_schema(table):
    if "key_schema" not in config:
        config.key_schema = {}
    if table.name not in config.key_schema:
        config.key_schema[table.name] = table.key_schema
    return config.key_schema[table.name]

def get(args):
    table = boto3.resource("dynamodb").Table(args.table)
    key_attr_name = get_key_schema(table)[0]["AttributeName"]
    return table.get_item(Key={key_attr_name: args.key[0]})["Item"]

parser_get = register_parser(get)
parser_get.add_argument("key", nargs="*")

def put(args):
    table = boto3.resource("dynamodb").Table(args.table)
    with table.batch_writer() as batch:
        for item in args.items:
            batch.put_item(Item=item)

parser_put = register_parser(put)
parser_put.add_argument("items", nargs="*", type=json.loads)

def paginate(boto3_paginator, *args, **kwargs):
    for page in boto3_paginator.paginate(*args, **kwargs):
        for result_key in boto3_paginator.result_keys:
            for value in page.get(result_key.parsed.get("value"), []):
                yield value

def scan(args):
    table = boto3.resource("dynamodb").Table(args.table)
    return table.scan()["Items"]

parser_scan = register_parser(scan)

main()
