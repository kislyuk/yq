#!/usr/bin/env python

import io
import os
import platform
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from yq import cli, yq  # noqa

USING_PYPY = True if platform.python_implementation() == "PyPy" else False

yaml_with_tags = """
foo: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  3766343436323632623130303
xyz: !!mytag
  foo: bar
  baz: 1
xyzzt: !binary
  - 1
  - 2
  - 3
scalar-red: !color FF0000
scalar-orange: !color FFFF00
mapping-red: !color-mapping {r: 255, g: 0, b: 0}
mapping-orange:
  !color-mapping
  r: 255
  g: 255
  b: 0
"""

bomb_yaml = """
lol1: &lol1 "lol"
lol2: &lol2 [*lol1,*lol1,*lol1,*lol1,*lol1,*lol1,*lol1,*lol1,*lol1]
lol3: &lol3 [*lol2,*lol2,*lol2,*lol2,*lol2,*lol2,*lol2,*lol2,*lol2]
lol4: &lol4 [*lol3,*lol3,*lol3,*lol3,*lol3,*lol3,*lol3,*lol3,*lol3]
lol5: &lol5 [*lol4,*lol4,*lol4,*lol4,*lol4,*lol4,*lol4,*lol4,*lol4]
lol6: &lol6 [*lol5,*lol5,*lol5,*lol5,*lol5,*lol5,*lol5,*lol5,*lol5]
lol7: &lol7 [*lol6,*lol6,*lol6,*lol6,*lol6,*lol6,*lol6,*lol6,*lol6]
lol8: &lol8 [*lol7,*lol7,*lol7,*lol7,*lol7,*lol7,*lol7,*lol7,*lol7]
lol9: &lol9 [*lol8,*lol8,*lol8,*lol8,*lol8,*lol8,*lol8,*lol8,*lol8]
lol10: &lol10 [*lol9,*lol9,*lol9,*lol9,*lol9,*lol9,*lol9,*lol9,*lol9]
"""


class TestYq(unittest.TestCase):
    def run_yq(self, input_data, args, expect_exit_codes={os.EX_OK}, input_format="yaml"):
        stdin, stdout = sys.stdin, sys.stdout
        try:
            if isinstance(input_data, str):
                sys.stdin = io.StringIO(input_data)
            else:
                sys.stdin = input_data
            sys.stdout = io.StringIO()
            cli(args, input_format=input_format)
        except SystemExit as e:
            self.assertIn(e.code, expect_exit_codes)
        finally:
            result = sys.stdout.getvalue()
            sys.stdin, sys.stdout = stdin, stdout
        return result

    def test_yq(self):
        for input_format in "yaml", "xml":
            try:
                cli(["--help"], input_format=input_format)
            except SystemExit as e:
                self.assertEqual(e.code, 0)
        self.assertEqual(self.run_yq("{}", ["."]), "")
        self.assertEqual(self.run_yq("foo:\n bar: 1\n baz: {bat: 3}", [".foo.baz.bat"]), "")
        self.assertEqual(self.run_yq("[1, 2, 3]", ["--yaml-output", "-M", "."]), "- 1\n- 2\n- 3\n")
        self.assertEqual(self.run_yq("foo:\n bar: 1\n baz: {bat: 3}", ["-y", ".foo.baz.bat"]), "3\n...\n")
        self.assertEqual(self.run_yq("[aaaaaaaaaa bbb]", ["-y", "."]), "- aaaaaaaaaa bbb\n")
        self.assertEqual(self.run_yq("[aaaaaaaaaa bbb]", ["-y", "-w", "8", "."]), "- aaaaaaaaaa\n  bbb\n")
        self.assertEqual(self.run_yq('{"понедельник": 1}', ['.["понедельник"]']), "")
        self.assertEqual(self.run_yq('{"понедельник": 1}', ["-y", '.["понедельник"]']), "1\n...\n")
        self.assertEqual(self.run_yq("- понедельник\n- вторник\n", ["-y", "."]), "- понедельник\n- вторник\n")

    def test_yq_err(self):
        err = (
            "yq: Error running jq: ScannerError: while scanning for the next token\nfound character '%' that "
            'cannot start any token\n  in "<file>", line 1, column 3.'
        )
        err2 = (
            "yq: Error running jq: ScannerError: while scanning for the next token\nfound character that "
            'cannot start any token\n  in "<file>", line 1, column 3.'
        )
        self.run_yq("- %", ["."], expect_exit_codes={err, err2, 2})

    def test_yq_arg_handling(self):
        from unittest import mock

        test_doc = os.path.join(os.path.dirname(__file__), "doc.yml")
        test_filter = os.path.join(os.path.dirname(__file__), "filter.jq")
        unusable_non_tty_input = mock.Mock()
        unusable_non_tty_input.isatty = mock.Mock(return_value=False)
        unusable_tty_input = mock.Mock()
        unusable_tty_input.isatty = mock.Mock(return_value=True)

        self.run_yq("{}", ["."])
        self.run_yq(unusable_non_tty_input, [".", test_doc])
        self.run_yq(unusable_non_tty_input, [".", test_doc, test_doc])
        self.run_yq("{}", ["-f", test_filter])
        self.run_yq(unusable_non_tty_input, ["-f", test_filter, test_doc])
        self.run_yq(unusable_non_tty_input, ["-f", test_filter, test_doc, test_doc])

        self.run_yq(unusable_tty_input, [], expect_exit_codes={2})
        self.run_yq(unusable_tty_input, ["."], expect_exit_codes={2})
        self.run_yq(unusable_tty_input, ["-f", test_filter], expect_exit_codes={2})

    def test_yq_arg_passthrough(self):
        self.assertEqual(self.run_yq("{}", ["--arg", "foo", "bar", "--arg", "x", "y", "--indent", "4", "."]), "")
        self.assertEqual(
            self.run_yq("{}", ["--arg", "foo", "bar", "--arg", "x", "y", "-y", "--indent", "4", ".x=$x"]), "x: y\n"
        )
        err = "yq: Error running jq: BrokenPipeError: [Errno 32] Broken pipe" + (": '<fdopen>'." if USING_PYPY else ".")
        self.run_yq("{}", ["--indent", "9", "."], expect_exit_codes={err, 2})
        self.assertEqual(self.run_yq("", ["true", "-y", "-rn"]), "true\n...\n")

        with tempfile.NamedTemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b".a")
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            for arg in "--from-file", "-f":
                tf2.seek(0)
                self.assertEqual(self.run_yq("", ["-y", arg, tf.name, self.fd_path(tf2)]), "1\n...\n")

    @unittest.skipIf(subprocess.check_output(["jq", "--version"]) < b"jq-1.6", "Test options introduced in jq 1.6")
    def test_jq16_arg_passthrough(self):
        self.assertEqual(
            self.run_yq("{}", ["--indentless", "-y", ".a=$ARGS.positional", "--args", "a", "b"]), "a:\n- a\n- b\n"
        )
        self.assertEqual(self.run_yq("{}", ["-y", ".a=$ARGS.positional", "--args", "a", "b"]), "a:\n  - a\n  - b\n")
        self.assertEqual(self.run_yq("{}", [".", "--jsonargs", "{}", "{}"]), "")

    def test_short_option_separation(self):
        # self.assertEqual(self.run_yq('{"a": 1}', ["-yCcC", "."]), "a: 1\n") - Fails on 2.7 and 3.8
        self.assertEqual(self.run_yq('{"a": 1}', ["-CcCy", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-y", "-CS", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-y", "-CC", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-y", "-cC", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-x", "-cC", "."]), "<a>1</a>\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-C", "."]), "")
        self.assertEqual(self.run_yq('{"a": 1}', ["-Cc", "."]), "")

    def fd_path(self, fh):
        return "/dev/fd/{}".format(fh.fileno())

    def test_multidocs(self):
        self.assertEqual(self.run_yq("---\na: b\n---\nc: d", ["-y", "."]), "a: b\n---\nc: d\n")
        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'{"a": "b"}')
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            tf2.seek(0)
            self.assertEqual(self.run_yq("", ["-y", ".a", self.fd_path(tf), self.fd_path(tf2)]), "b\n--- 1\n...\n")

    def test_datetimes(self):
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["."]), "")
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "."]), "- '2016-12-20T22:07:36Z'\n")
        self.assertEqual(
            self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "--yml-out-ver=1.2", "."]), "- 2016-12-20T22:07:36Z\n"
        )
        self.assertEqual(self.run_yq("2016-12-20", ["."]), "")
        self.assertEqual(self.run_yq("2016-12-20", ["-y", "."]), "'2016-12-20'\n")
        self.assertEqual(self.run_yq("2016-12-20", ["-y", "--yml-out-ver=1.2", "."]), "2016-12-20\n...\n")

    def test_unrecognized_tags(self):
        self.assertEqual(self.run_yq("!!foo bar\n", ["."]), "")
        self.assertEqual(self.run_yq("!!foo bar\n", ["-y", "."]), "bar\n...\n")
        self.assertEqual(self.run_yq("x: !foo bar\n", ["-y", "."]), "x: bar\n")
        self.assertEqual(self.run_yq("x: !!foo bar\n", ["-y", "."]), "x: bar\n")
        with tempfile.TemporaryFile() as tf:
            tf.write(yaml_with_tags.encode())
            tf.seek(0)
            self.assertEqual(self.run_yq("", ["-y", ".xyz.foo", self.fd_path(tf)]), "bar\n...\n")

    def test_roundtrip_yaml(self):
        cfn_filename = os.path.join(os.path.dirname(__file__), "cfn.yml")
        with io.open(cfn_filename) as fh:
            self.assertEqual(self.run_yq("", ["-Y", ".", cfn_filename]), fh.read())

    def test_in_place_yaml(self):
        with tempfile.NamedTemporaryFile() as tf, tempfile.NamedTemporaryFile() as tf2:
            tf.write(b"- foo\n- bar\n")
            tf.seek(0)
            tf2.write(b"- foo\n- bar\n")
            tf2.seek(0)
            self.run_yq("", ["-i", "-y", ".[0]", tf.name, tf2.name])
            self.assertEqual(tf.read(), b"foo\n...\n")
            self.assertEqual(tf2.read(), b"foo\n...\n")

            # Files do not get overwritten on error
            self.run_yq("", ["-i", "-y", tf.name, tf2.name], expect_exit_codes=[3])
            tf.seek(0)
            tf2.seek(0)
            self.assertEqual(tf.read(), b"foo\n...\n")
            self.assertEqual(tf2.read(), b"foo\n...\n")

    def test_in_place_toml(self):
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(b'[GLOBAL]\nversion="1.0.0"\n')
            tf.seek(0)
            self.run_yq("", ["-i", "-t", '.GLOBAL.version="1.0.1"', tf.name], input_format="toml")
            self.assertEqual(tf.read(), b'[GLOBAL]\nversion = "1.0.1"\n')

    def test_explicit_doc_markers(self):
        test_doc = os.path.join(os.path.dirname(__file__), "doc.yml")
        self.assertTrue(self.run_yq("", ["-y", ".", test_doc]).startswith("yaml_struct"))
        self.assertTrue(self.run_yq("", ["-y", "--explicit-start", ".", test_doc]).startswith("---"))
        self.assertTrue(self.run_yq("", ["-y", "--explicit-end", ".", test_doc]).endswith("...\n"))

    def test_xq(self):
        self.assertEqual(self.run_yq("<foo/>", ["."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["--xml-item-depth=2", "."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["--xml-dtd", "."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["-x", ".foo.x=1"], input_format="xml"), "<foo>\n  <x>1</x>\n</foo>\n")
        self.assertTrue(self.run_yq("<foo/>", ["-x", "--xml-dtd", "."], input_format="xml").startswith("<?xml"))
        self.assertTrue(self.run_yq("<foo/>", ["-x", "--xml-root=R", "."], input_format="xml").startswith("<R>"))
        self.assertEqual(self.run_yq("<foo/>", ["--xml-force-list=foo", "."], input_format="xml"), "")

        self.assertEqual(self.run_yq("<a><b/></a>", ["-y", "."], input_format="xml"), "a:\n  b: null\n")
        self.assertEqual(
            self.run_yq("<a><b/></a>", ["-y", "--xml-force-list", "b", "."], input_format="xml"),
            "a:\n  b:\n    - null\n",
        )

        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b"<a><b/></a>")
            tf.seek(0)
            tf2.write(b"<a><c/></a>")
            tf2.seek(0)
            self.assertEqual(
                self.run_yq("", ["-x", ".a", self.fd_path(tf), self.fd_path(tf2)], input_format="xml"),
                "<b></b>\n<c></c>\n",
            )
        err = (
            "yq: Error converting JSON to XML: cannot represent non-object types at top level. "
            "Use --xml-root=name to envelope your output with a root element."
        )
        self.run_yq("[1]", ["-x", "."], expect_exit_codes=[err])

    def test_xq_dtd(self):
        with tempfile.TemporaryFile() as tf:
            tf.write(b'<a><b c="d">e</b><b>f</b></a>')
            tf.seek(0)
            self.assertEqual(
                self.run_yq("", ["-x", ".a", self.fd_path(tf)], input_format="xml"), '<b c="d">e</b><b>f</b>\n'
            )
            tf.seek(0)
            self.assertEqual(
                self.run_yq("", ["-x", "--xml-dtd", ".", self.fd_path(tf)], input_format="xml"),
                '<?xml version="1.0" encoding="utf-8"?>\n<a>\n  <b c="d">e</b>\n  <b>f</b>\n</a>\n',
            )
            tf.seek(0)
            self.assertEqual(
                self.run_yq("", ["-x", "--xml-dtd", "--xml-root=g", ".a", self.fd_path(tf)], input_format="xml"),
                '<?xml version="1.0" encoding="utf-8"?>\n<g>\n  <b c="d">e</b>\n  <b>f</b>\n</g>\n',
            )

    def test_tomlq(self):
        self.assertEqual(self.run_yq("[foo]\nbar = 1", ["."], input_format="toml"), "")
        self.assertEqual(self.run_yq("[foo]\nbar = 1", ["-t", ".foo"], input_format="toml"), "bar = 1\n")
        self.assertEqual(self.run_yq("[foo]\nbar = 2020-02-20", ["."], input_format="toml"), "")

    def test_abbrev_opt_collisions(self):
        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            self.assertEqual(
                self.run_yq("", ["-y", "-e", "--slurp", ".[0] == .[1]", "-", self.fd_path(tf), self.fd_path(tf2)]),
                "true\n...\n",
            )

    def test_entity_expansion_defense(self):
        self.run_yq(bomb_yaml, ["."], expect_exit_codes=["yq: Error: detected unsafe YAML entity expansion"])

    def test_yaml_type_tags(self):
        bin_yaml = "example: !!binary Zm9vYmFyCg=="
        self.assertEqual(self.run_yq(bin_yaml, ["."]), "")
        self.assertEqual(self.run_yq(bin_yaml, ["-y", "."]), "example: Zm9vYmFyCg==\n")
        set_yaml = "example: !!set { Boston Red Sox, Detroit Tigers, New York Yankees }"
        self.assertEqual(self.run_yq(set_yaml, ["."]), "")
        self.assertEqual(
            self.run_yq(set_yaml, ["-y", "."]),
            "example:\n  Boston Red Sox: null\n  Detroit Tigers: null\n  New York Yankees: null\n",
        )

    def test_yaml_merge(self):
        self.assertEqual(
            self.run_yq("a: &b\n  c: d\ne:\n  <<: *b\n  g: h", ["-y", "."]), "a:\n  c: d\ne:\n  c: d\n  g: h\n"
        )

    def test_yaml_floats(self):
        self.assertEqual(self.run_yq("test: 0.0004", ["-y", "."]), "test: 0.0004\n")

    def test_yaml_1_2(self):
        self.assertEqual(self.run_yq("11:12:13", ["."]), "")
        self.assertEqual(self.run_yq("11:12:13", ["-y", "."]), "'11:12:13'\n")

        self.assertEqual(self.run_yq("on: 12:34:56", ["-y", "."]), "'on': '12:34:56'\n")
        self.assertEqual(self.run_yq("on: 12:34:56", ["-y", "--yml-out-ver=1.2", "."]), "on: 12:34:56\n")

        self.assertEqual(self.run_yq("2022-02-22", ["-y", "."]), "'2022-02-22'\n")
        self.assertEqual(self.run_yq("2022-02-22", ["-y", "--yml-out-ver=1.2", "."]), "2022-02-22\n...\n")

        self.assertEqual(self.run_yq("0b1010_0111", ["-y", "."]), "'0b1010_0111'\n")
        self.assertEqual(self.run_yq("0b1010_0111", ["-y", "--yml-out-ver=1.2", "."]), "0b1010_0111\n...\n")

        self.assertEqual(self.run_yq("0x_0A_74_AE", ["-y", "."]), "'0x_0A_74_AE'\n")
        self.assertEqual(self.run_yq("0x_0A_74_AE", ["-y", "--yml-out-ver=1.2", "."]), "0x_0A_74_AE\n...\n")

        self.assertEqual(self.run_yq("+685_230", ["-y", "."]), "'+685_230'\n")
        self.assertEqual(self.run_yq("+685_230", ["-y", "--yml-out-ver=1.2", "."]), "+685_230\n...\n")

        self.assertEqual(self.run_yq("+12345", ["-y", "."]), "12345\n...\n")

    def test_yaml_1_1_octals(self):
        self.assertEqual(self.run_yq("on: -012345", ["-y", "."]), "'on': -5349\n")
        self.assertEqual(self.run_yq("on: '0900'", ["-y", "."]), "'on': '0900'\n")

    @unittest.expectedFailure
    def test_yaml_1_2_octals(self):
        """YAML 1.2 octals not yet implemented"""
        self.assertEqual(self.run_yq("on: -012345", ["-y", "--yml-out-ver=1.2", "."]), "on: -12345\n")


if __name__ == "__main__":
    unittest.main()
