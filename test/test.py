#!/usr/bin/env python
# coding: utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, unittest, tempfile, json, io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from yq import main

USING_PYTHON2 = True if sys.version_info < (3, 0) else False

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

if __name__ == '__main__':
    unittest.main()
