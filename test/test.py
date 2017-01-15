#!/usr/bin/env python
# coding: utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, unittest, tempfile, json, io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from yq import main

class TestYq(unittest.TestCase):
    def test_basic_statements(self):
        try:
            orig_stdin = sys.stdin
            sys.stdin = io.StringIO("foo:\n bar: 1\n baz: {bat: 3}")
            main([".foo.baz.bat"])
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_OK)
        finally:
            sys.stdin = orig_stdin

if __name__ == '__main__':
    unittest.main()
