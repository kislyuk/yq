#!/usr/bin/env python
# coding: utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, unittest, tempfile, json, io, platform

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from yq import main # noqa

USING_PYTHON2 = True if sys.version_info < (3, 0) else False
USING_PYPY = True if platform.python_implementation() == "PyPy" else False

class TestYq(unittest.TestCase):
    def run_yq(self, input_data, args, expect_exit_code=os.EX_OK):
        stdin, stdout = sys.stdin, sys.stdout
        try:
            sys.stdin = io.StringIO(input_data)
            sys.stdout = io.BytesIO() if USING_PYTHON2 else io.StringIO()
            main(args)
        except SystemExit as e:
            self.assertEqual(e.code, expect_exit_code)
        finally:
            result = sys.stdout.getvalue()
            if USING_PYTHON2:
                result = result.decode("utf-8")
            sys.stdin, sys.stdout = stdin, stdout
        return result

    def test_yq(self):
        self.assertEqual(self.run_yq("{}", ["."]), "")
        self.assertEqual(self.run_yq("foo:\n bar: 1\n baz: {bat: 3}", [".foo.baz.bat"]), "")
        self.assertEqual(self.run_yq("[1, 2, 3]", ["--yaml-output", "-M", "."]), "- 1\n- 2\n- 3\n")
        self.assertEqual(self.run_yq("foo:\n bar: 1\n baz: {bat: 3}", ["-y", ".foo.baz.bat"]), "3\n...\n")
        self.assertEqual(self.run_yq("[aaaaaaaaaa bbb]", ["-y", "."]), "- aaaaaaaaaa bbb\n")
        self.assertEqual(self.run_yq("[aaaaaaaaaa bbb]", ["-y", "-w8", "."]), "- aaaaaaaaaa\n  bbb\n")
        self.assertEqual(self.run_yq('{"понедельник": 1}', ['.["понедельник"]']), "")
        self.assertEqual(self.run_yq('{"понедельник": 1}', ["-y", '.["понедельник"]']), "1\n...\n")
        self.assertEqual(self.run_yq("- понедельник\n- вторник\n", ["-y", "."]), "- понедельник\n- вторник\n")

    def test_yq_err(self):
        err = 'yq: Error running jq: ScannerError: while scanning for the next token\nfound character \'%\' that cannot start any token\n  in "<file>", line 1, column 3.'
        self.run_yq("- %", ["."], expect_exit_code=err)

    def test_yq_arg_passthrough(self):
        self.assertEqual(self.run_yq("{}", ["--arg", "foo", "bar", "--arg", "x", "y", "--indent", "4", "."]), "")
        self.assertEqual(self.run_yq("{}", ["--arg", "foo", "bar", "--arg", "x", "y", "-y", "--indent", "4", ".x=$x"]),
                         "x: y\n")
        err = "yq: Error running jq: {}Error: [Errno 32] Broken pipe{}".format("IO" if USING_PYTHON2 else "BrokenPipe",
                                                                               ": '<fdopen>'." if USING_PYPY else ".")
        self.run_yq("{}", ["--indent", "9", "."], expect_exit_code=err)

        with tempfile.NamedTemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'.a')
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            for arg in "--from-file", "-f":
                tf2.seek(0)
                self.assertEqual(self.run_yq("", ["-y", arg, tf.name, self.fd_path(tf2)]), '1\n...\n')

    def fd_path(self, fh):
        return "/dev/fd/{}".format(fh.fileno())

    def test_multidocs(self):
        self.assertEqual(self.run_yq("---\na: b\n---\nc: d", ["-y", "."]), "a: b\n---\nc: d\n")
        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'{"a": "b"}')
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            tf2.seek(0)
            self.assertEqual(self.run_yq("", ["-y", ".a", self.fd_path(tf), self.fd_path(tf2)]), 'b\n--- 1\n...\n')

    def test_datetimes(self):
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["."]), "")
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "."]), "- '2016-12-20T22:07:36'\n")

        self.assertEqual(self.run_yq("2016-12-20", ["."]), "")
        self.assertEqual(self.run_yq("2016-12-20", ["-y", "."]), "'2016-12-20'\n")

    @unittest.expectedFailure
    def test_times(self):
        """
        Timestamps are parsed as sexagesimals in YAML 1.1 but not 1.2. No PyYAML support for YAML 1.2 yet. See issue 10
        """
        self.assertEqual(self.run_yq("11:12:13", ["."]), "")
        self.assertEqual(self.run_yq("11:12:13", ["-y", "."]), "'11:12:13'\n")

if __name__ == '__main__':
    unittest.main()
