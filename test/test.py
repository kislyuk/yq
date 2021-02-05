#!/usr/bin/env python

import os, sys, unittest, tempfile, io, platform, subprocess, yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from yq import yq, cli  # noqa

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
        err = ('yq: Error running jq: ScannerError: while scanning for the next token\nfound character \'%\' that '
               'cannot start any token\n  in "<file>", line 1, column 3.')
        self.run_yq("- %", ["."], expect_exit_codes={err, 2})

    @unittest.skipIf(sys.version_info < (3, 5), "Skipping test incompatible with Python 2")
    def test_yq_arg_handling(self):
        from unittest import mock

        test_doc = os.path.join(os.path.dirname(__file__), "doc.yml")
        test_filter = os.path.join(os.path.dirname(__file__), "filter.jq")
        unusable_non_tty_input = mock.Mock()
        unusable_non_tty_input.isatty = mock.Mock(return_value=False)
        unusable_tty_input = mock.Mock()
        unusable_tty_input.isatty = mock.Mock(return_value=True)

        self.run_yq("{}", [], expect_exit_codes={0} if sys.stdin.isatty() else {2})
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
        self.assertEqual(self.run_yq("{}", ["--arg", "foo", "bar", "--arg", "x", "y", "-y", "--indent", "4", ".x=$x"]),
                         "x: y\n")
        err = "yq: Error running jq: BrokenPipeError: [Errno 32] Broken pipe" + (": '<fdopen>'." if USING_PYPY else ".")
        self.run_yq("{}", ["--indent", "9", "."], expect_exit_codes={err, 2})

        with tempfile.NamedTemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'.a')
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            for arg in "--from-file", "-f":
                tf2.seek(0)
                self.assertEqual(self.run_yq("", ["-y", arg, tf.name, self.fd_path(tf2)]), '1\n...\n')

    @unittest.skipIf(subprocess.check_output(["jq", "--version"]) < b"jq-1.6", "Test options introduced in jq 1.6")
    def test_jq16_arg_passthrough(self):
        self.assertEqual(self.run_yq("{}", ["--indentless", "-y", ".a=$ARGS.positional", "--args", "a", "b"]),
                         "a:\n- a\n- b\n")
        self.assertEqual(self.run_yq("{}", ["-y", ".a=$ARGS.positional", "--args", "a", "b"]), "a:\n  - a\n  - b\n")
        self.assertEqual(self.run_yq("{}", [".", "--jsonargs", "a", "b"]), "")

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
            self.assertEqual(self.run_yq("", ["-y", ".a", self.fd_path(tf), self.fd_path(tf2)]), 'b\n--- 1\n...\n')

    def test_datetimes(self):
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["."]), "")
        if yaml.__version__ < '5.3':
            self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "."]), "- '2016-12-20T22:07:36'\n")
        else:
            self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "."]), "- '2016-12-20T22:07:36+00:00'\n")

        self.assertEqual(self.run_yq("2016-12-20", ["."]), "")
        self.assertEqual(self.run_yq("2016-12-20", ["-y", "."]), "'2016-12-20'\n")

    def test_unrecognized_tags(self):
        self.assertEqual(self.run_yq("!!foo bar\n", ["."]), "")
        self.assertEqual(self.run_yq("!!foo bar\n", ["-y", "."]), "bar\n...\n")
        self.assertEqual(self.run_yq("x: !foo bar\n", ["-y", "."]), "x: bar\n")
        self.assertEqual(self.run_yq("x: !!foo bar\n", ["-y", "."]), "x: bar\n")
        with tempfile.TemporaryFile() as tf:
            tf.write(yaml_with_tags.encode())
            tf.seek(0)
            self.assertEqual(self.run_yq("", ["-y", ".xyz.foo", self.fd_path(tf)]), 'bar\n...\n')

    def test_roundtrip_yaml(self):
        cfn_filename = os.path.join(os.path.dirname(__file__), "cfn.yml")
        with io.open(cfn_filename) as fh:
            self.assertEqual(self.run_yq("", ["-Y", ".", cfn_filename]), fh.read())

    @unittest.skipIf(sys.version_info < (3, 5), "Skipping feature incompatible with Python 2")
    def test_in_place(self):
        with tempfile.NamedTemporaryFile() as tf, tempfile.NamedTemporaryFile() as tf2:
            tf.write(b"- foo\n- bar\n")
            tf.seek(0)
            tf2.write(b"- foo\n- bar\n")
            tf2.seek(0)
            self.run_yq("", ["-i", "-y", ".[0]", tf.name, tf2.name])
            self.assertEqual(tf.read(), b'foo\n...\n')
            self.assertEqual(tf2.read(), b'foo\n...\n')

            # Files do not get overwritten on error (DeferredOutputStream logic)
            self.run_yq("", ["-i", "-y", tf.name, tf2.name], expect_exit_codes=[3])
            tf.seek(0)
            tf2.seek(0)
            self.assertEqual(tf.read(), b'foo\n...\n')
            self.assertEqual(tf2.read(), b'foo\n...\n')

    def test_explicit_doc_markers(self):
        test_doc = os.path.join(os.path.dirname(__file__), "doc.yml")
        self.assertTrue(self.run_yq("", ["-y", ".", test_doc]).startswith("yaml_struct"))
        self.assertTrue(self.run_yq("", ["-y", "--explicit-start", ".", test_doc]).startswith("---"))
        self.assertTrue(self.run_yq("", ["-y", "--explicit-end", ".", test_doc]).endswith("...\n"))

    @unittest.expectedFailure
    def test_times(self):
        """
        Timestamps are parsed as sexagesimals in YAML 1.1 but not 1.2. No PyYAML support for YAML 1.2 yet. See issue 10
        """
        self.assertEqual(self.run_yq("11:12:13", ["."]), "")
        self.assertEqual(self.run_yq("11:12:13", ["-y", "."]), "'11:12:13'\n")

    def test_xq(self):
        self.assertEqual(self.run_yq("<foo/>", ["."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["-x", ".foo.x=1"], input_format="xml"),
                         '<foo>\n  <x>1</x>\n</foo>\n')

        self.assertEqual(self.run_yq("<a><b/></a>", ["-y", "."], input_format="xml"),
                         "a:\n  b: null\n")
        self.assertEqual(self.run_yq("<a><b/></a>", ["-y", "--xml-force-list", "b", "."], input_format="xml"),
                         "a:\n  b:\n    - null\n")

        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'<a><b/></a>')
            tf.seek(0)
            tf2.write(b'<a><c/></a>')
            tf2.seek(0)
            self.assertEqual(self.run_yq("", ["-x", ".a", self.fd_path(tf), self.fd_path(tf2)], input_format="xml"),
                             '<b></b>\n<c></c>\n')
        err = ("yq: Error converting JSON to XML: cannot represent non-object types at top level. "
               "Use --xml-root=name to envelope your output with a root element.")
        self.run_yq("[1]", ["-x", "."], expect_exit_codes=[err])

    def test_xq_dtd(self):
        with tempfile.TemporaryFile() as tf:
            tf.write(b'<a><b c="d">e</b><b>f</b></a>')
            tf.seek(0)
            self.assertEqual(self.run_yq("", ["-x", ".a", self.fd_path(tf)], input_format="xml"),
                             '<b c="d">e</b><b>f</b>\n')
            tf.seek(0)
            self.assertEqual(self.run_yq("", ["-x", "--xml-dtd", ".", self.fd_path(tf)], input_format="xml"),
                             '<?xml version="1.0" encoding="utf-8"?>\n<a>\n  <b c="d">e</b>\n  <b>f</b>\n</a>\n')
            tf.seek(0)
            self.assertEqual(
                self.run_yq("", ["-x", "--xml-dtd", "--xml-root=g", ".a", self.fd_path(tf)], input_format="xml"),
                '<?xml version="1.0" encoding="utf-8"?>\n<g>\n  <b c="d">e</b>\n  <b>f</b>\n</g>\n'
            )

    def test_tomlq(self):
        self.assertEqual(self.run_yq("[foo]\nbar = 1", ["."], input_format="toml"), "")
        self.assertEqual(self.run_yq("[foo]\nbar = 1", ["-t", ".foo"], input_format="toml"), "bar = 1\n")

    @unittest.skipIf(sys.version_info < (3, 5),
                     "argparse option abbreviation interferes with opt passthrough, can't be disabled until Python 3.5")
    def test_abbrev_opt_collisions(self):
        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            self.assertEqual(
                self.run_yq("", ["-y", "-e", "--slurp", ".[0] == .[1]", "-", self.fd_path(tf), self.fd_path(tf2)]),
                "true\n...\n"
            )

if __name__ == '__main__':
    unittest.main()
