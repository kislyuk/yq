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

USING_PYPY = platform.python_implementation() == "PyPy"

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
    def run_yq(self, input_data, args, expect_exit_codes=None, input_format="yaml"):
        if expect_exit_codes is None:
            expect_exit_codes = {os.EX_OK}
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
        long_string = " ".join(["word"] * 30)
        self.assertEqual(self.run_yq(f'["{long_string}"]', ["-y", "--width", "0", "."]), f"- {long_string}\n")
        self.assertEqual(self.run_yq(f'["{long_string}"]', ["-Y", "--width", "0", "."]), f'- "{long_string}"\n')
        self.assertEqual(self.run_yq('{"понедельник": 1}', ['.["понедельник"]']), "")
        self.assertEqual(self.run_yq('{"понедельник": 1}', ["-y", '.["понедельник"]']), "1\n...\n")
        self.assertEqual(self.run_yq("- понедельник\n- вторник\n", ["-y", "."]), "- понедельник\n- вторник\n")

    def test_version(self):
        from unittest import mock

        with mock.patch("yq.parser.__version__", "1.2.3"), mock.patch(
            "yq.parser.subprocess.check_output", return_value="jq-1.7\n"
        ):
            self.assertEqual(self.run_yq("", ["--version"]), "yq 1.2.3\njq-1.7\n")

        with mock.patch("yq.parser.__version__", "1.2.3"), mock.patch(
            "yq.parser.subprocess.check_output", side_effect=OSError("jq not found")
        ):
            self.assertEqual(
                self.run_yq("", ["--version"]),
                "yq 1.2.3\njq version could not be determined: jq not found\n",
            )

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

    def test_yq_long_null_input_passthrough(self):
        from unittest import mock

        unusable_tty_input = mock.Mock()
        unusable_tty_input.isatty = mock.Mock(return_value=True)

        self.assertEqual(self.run_yq(unusable_tty_input, ["--null-input", "-y", "."]), "null\n...\n")

    def test_null_input_closed_on_error(self):
        from unittest import mock

        with mock.patch("yq.yq", side_effect=SystemExit(1)) as run:
            self.run_yq("", ["--null-input", "."], expect_exit_codes={1})
        self.assertTrue(run.call_args.kwargs["input_streams"][0].closed)

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
        return f"/dev/fd/{fh.fileno()}"

    def test_multidocs(self):
        self.assertEqual(self.run_yq("---\na: b\n---\nc: d", ["-y", "."]), "---\na: b\n---\nc: d\n")
        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'{"a": "b"}')
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            tf2.seek(0)
            self.assertEqual(
                self.run_yq("", ["-y", ".a", self.fd_path(tf), self.fd_path(tf2)]), "---\nb\n---\n1\n...\n"
            )

    def test_leading_document_marker(self):
        for mode in "-y", "-Y":
            with self.subTest(mode=mode):
                self.assertEqual(self.run_yq("a: b\n", [mode, "."]), "a: b\n")
                self.assertEqual(self.run_yq("---\na: b\n", [mode, "."]), "---\na: b\n")
                self.assertEqual(self.run_yq("%YAML 1.1\n---\na: b\n", [mode, "."]), "---\na: b\n")
                self.assertTrue(self.run_yq("# header\n---\na: b\n", [mode, "."]).startswith("---\n"))
                self.assertEqual(self.run_yq("a: b\n---\nc: d\n", [mode, "."]), "---\na: b\n---\nc: d\n")
                self.assertEqual(self.run_yq("a: b\n", [mode, "., ."]), "---\na: b\n---\na: b\n")
                self.assertEqual(self.run_yq("a: b\n---\nc: d\n", [mode, "select(.a)"]), "---\na: b\n")
                self.assertEqual(self.run_yq("---\na: b\n", [mode, "empty"]), "")
                self.assertEqual(self.run_yq("", [mode, "."]), "")

    def test_document_marker_newline(self):
        import yaml

        for mode in "-y", "-Y":
            for indent in [], ["--indentless"]:
                for document in "hello", "42", "null", "[]", "{}", "[one, two]", "{a: b}":
                    with self.subTest(mode=mode, indent=indent, document=document):
                        result = self.run_yq(document, [mode, *indent, "--explicit-start", "."])
                        self.assertTrue(result.startswith("---\n"), result)
                        self.assertEqual(yaml.safe_load(result), yaml.safe_load(document))
                        result = self.run_yq("a: b\n---\n" + document, [mode, *indent, "."])
                        self.assertIn("\n---\n", result)
                        self.assertNotIn("--- ", result)

    def test_datetimes(self):
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["."]), "")
        self.assertEqual(self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "."]), "- '2016-12-20T22:07:36Z'\n")
        self.assertEqual(
            self.run_yq("- 2016-12-20T22:07:36Z\n", ["-y", "--yml-out-ver=1.2", "."]), "- 2016-12-20T22:07:36Z\n"
        )
        self.assertEqual(self.run_yq("2016-12-20", ["."]), "")
        self.assertEqual(self.run_yq("2016-12-20", ["-y", "."]), "'2016-12-20'\n")
        self.assertEqual(self.run_yq("2016-12-20", ["-y", "--yml-out-ver=1.2", "."]), "2016-12-20\n...\n")

    def test_yaml_frontmatter(self):
        header = "---\ntitle: My First Post\ndate: 2026-09-18\ntags: [notes, guides]\ndraft: false\n"
        body = "---\n# Hello World\nThis is the main content of the file.\n"
        expected_header = header.replace("2026-09-18", "'2026-09-18'").replace("draft: false", "draft: true")
        for flag in "--yaml-frontmatter", "-F":
            self.assertEqual(self.run_yq(header + body, ["-Y", flag, ".draft = true"]), expected_header + body)
        self.assertEqual(self.run_yq(header + body, ["-YF", ".draft = true"]), expected_header + body)
        self.assertEqual(self.run_yq(header + body, ["-cYF", ".draft = true"]), expected_header + body)

        # The body is not YAML and must never reach the scanner, even with control characters.
        body = "--- # closing fence\n# Heading\n```\n[unclosed\n\t@invalid: :\n\x00\n---\n...\n  spaces  \nno final newline"
        for mode in "-y", "-Y":
            self.assertEqual(self.run_yq("---\na: b\n" + body, [mode, "-F", "."]), "---\na: b\n" + body)
            self.assertEqual(
                self.run_yq("a: b\n--- inline body\n[invalid", [mode, "-F", "."]),
                "---\na: b\n--- inline body\n[invalid",
            )

    def test_yaml_frontmatter_boundaries(self):
        for mode in "-y", "-Y":
            for closing in "---\n", "---", "...\n", "... # end\n":
                for header, expected in [("---\na: b\n", "a: b\n"), ("a: b\n", "a: b\n"), ("---\nhello\n", "hello\n")]:
                    with self.subTest(mode=mode, header=header, closing=closing):
                        self.assertEqual(self.run_yq(header + closing, [mode, "-F", "."]), "---\n" + expected + closing)
            self.assertEqual(self.run_yq("---\n---\n# body", [mode, "-F", "."]), "---\nnull\n---\n# body")
            self.assertEqual(self.run_yq("a: b\n", [mode, "-F", "."]), "a: b\n")
            self.assertEqual(self.run_yq("---\na: b\n", [mode, "-F", "."]), "---\na: b\n")
            for closing in "---\n", "...\n":
                expected = "---\na: b\n...\n" + ("---\n" if closing == "---\n" else "") + "# body"
                self.assertEqual(
                    self.run_yq("---\na: b\n" + closing + "# body", [mode, "-F", "--explicit-end", "."]), expected
                )
        header = '# header\n---\ntext: |\n  ---\n  ...\nquoted: "---"\n'
        body = "---\n# body\n"
        self.assertEqual(
            self.run_yq(header + body, ["-YF", "."]), header.replace("# header\n---", "---\n# header") + body
        )

    def test_yaml_frontmatter_json(self):
        result = subprocess.check_output(
            [sys.executable, "-m", "yq", "-F", "-r", ".title"],
            input=b"---\ntitle: Hello\n---\n# body\n[invalid YAML",
        )
        self.assertEqual(result, b"Hello\n")

    def test_yaml_frontmatter_streaming(self):
        header = "---\na: b\n---\r\n"
        expected_header = "---\na: c\n---\r\n"
        # A body longer than several copy buffers, including a long line and no final newline.
        body = "# body\r\n" + "x" * (256 * 1024) + "\r\ntrailing spaces  "
        test = self

        class StreamingInput(io.StringIO):
            def seekable(self):
                return False

            def seek(self, *args):
                raise AssertionError("Frontmatter streaming must not seek the input")

            def read(self, size=-1):
                test.assertGreater(size, 0, "The body must be read in bounded chunks")
                test.assertLessEqual(size, 64 * 1024)
                # The header must be processed before the body is read, and each chunk
                # must be written before the next read instead of collecting the body.
                test.assertEqual(sys.stdout.getvalue(), expected_header + body[: self.tell() - len(header)])
                return super().read(size)

        for mode in "-yF", "-YF":
            with self.subTest(mode=mode):
                result = self.run_yq(StreamingInput(header + body), [mode, '.a = "c"'])
                self.assertEqual(result, expected_header + body)

    def test_yaml_frontmatter_in_place(self):
        with tempfile.NamedTemporaryFile() as first, tempfile.NamedTemporaryFile() as second:
            body = b"---\r\n# Heading\r\n\r\n[invalid YAML\r\n" + b"x" * (256 * 1024)
            body += b"\r\ntrailing spaces  \r\nno final newline"
            for stream in first, second:
                stream.write(b"---\r\na: b\r\n" + body)
                stream.flush()
            self.run_yq("", ["-iYF", '.a = "c"', first.name, second.name])
            for stream in first, second:
                stream.seek(0)
                self.assertEqual(stream.read(), b"---\na: c\n" + body)

            err = (
                "yq: Error running jq: ValueError: --yaml-frontmatter requires the jq filter "
                "to produce exactly one document."
            )
            for jq_filter, exit_code in [("empty", err), ("., .", err), ("[", 3)]:
                self.run_yq("", ["-iYF", jq_filter, first.name], expect_exit_codes={exit_code})
                first.seek(0)
                self.assertEqual(first.read(), b"---\na: c\n" + body)

            self.run_yq(
                "",
                ["-YF", ".", first.name, second.name],
                expect_exit_codes={"yq: --yaml-frontmatter requires one input file, or --in-place for multiple files"},
            )

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
        with open(cfn_filename) as fh:
            self.assertEqual(self.run_yq("", ["-Y", ".", cfn_filename]), fh.read())

    def test_yaml_comment_roundtrip(self):
        yaml_doc = (
            "# top\n"
            "a: 1 # inline a\n"
            "# before b\n"
            "b: 2\n"
            "parent: # parent inline\n"
            "  # child before\n"
            "  child: 3 # child inline\n"
            "items:\n"
            "  - 1 # one\n"
            "  # before two\n"
            "  - 2\n"
        )
        self.assertEqual(self.run_yq(yaml_doc, ["-Y", "."]), yaml_doc)
        self.assertEqual(
            self.run_yq(yaml_doc, ["-y", "."]),
            "a: 1\nb: 2\nparent:\n  child: 3\nitems:\n  - 1\n  - 2\n",
        )

        from yq.loader import get_loader
        from yq.yaml_support import CommentPreservingLoader

        self.assertNotIn(CommentPreservingLoader, get_loader(use_annotations=False).__mro__)
        self.assertIn(CommentPreservingLoader, get_loader(use_annotations=True).__mro__)

    def test_yaml_comments_released_per_document(self):
        from yq.loader import get_loader

        documents = [
            "# mapping\nvalue: 1 # inline\n# trailing mapping\n",
            "# sequence\n- item # inline\n# trailing sequence\n",
            "# scalar\nscalar # unattached inline\n# trailing scalar\n",
            "# empty document\n",
            "# empty collection\n[] # unattached inline\n",
        ] * 100
        source = "".join("---\n" + document for document in documents)
        for expand_aliases in True, False:
            with self.subTest(expand_aliases=expand_aliases):
                loader = get_loader(use_annotations=True, expand_aliases=expand_aliases)(io.StringIO(source))
                try:
                    for _ in documents:
                        self.assertTrue(loader.check_node())
                        self.assertEqual(loader.yaml_comments, [])
                        loader.construct_document(loader.get_node())
                    self.assertFalse(loader.check_node())
                    self.assertEqual(loader.yaml_comments, [])
                finally:
                    loader.dispose()

    def test_yaml_comment_cleanup_preserves_leading_comments(self):
        import yaml

        from yq.dumper import get_dumper
        from yq.loader import get_loader

        source = "# first\nvalue: 1 # inline\n... # end first\n# second\n---\nvalue: 2 # keep\n"
        for expand_aliases in True, False:
            with self.subTest(expand_aliases=expand_aliases):
                loader = get_loader(use_annotations=True, expand_aliases=expand_aliases)(io.StringIO(source))
                try:
                    self.assertTrue(loader.check_node())
                    first = loader.construct_document(loader.get_node())
                    # Advancing clears the completed document's comments before
                    # scanning the next document's leading comments.
                    self.assertTrue(loader.check_node())
                    self.assertEqual([comment.value for comment in loader.yaml_comments], [" end first", " second"])
                    second = loader.construct_document(loader.get_node())
                    self.assertFalse(loader.check_node())
                    self.assertEqual(loader.yaml_comments, [])
                    self.assertEqual(
                        yaml.dump_all(
                            [first, second], Dumper=get_dumper(use_annotations=True), default_flow_style=False
                        ),
                        "# first\nvalue: 1 # inline\n---\n# second\nvalue: 2 # keep\n",
                    )
                finally:
                    loader.dispose()

    def test_yaml_comment_cleanup_preserves_single_document(self):
        import yaml

        from yq.dumper import get_dumper
        from yq.loader import get_loader

        for start in "", "---\n", "%YAML 1.2\n---\n":
            for end in "", "...\n":
                with self.subTest(start=start, end=end):
                    source = "# leading\n" + start + "value: 1 # inline\n" + end
                    document = yaml.load(source, Loader=get_loader(use_annotations=True))
                    self.assertEqual(
                        yaml.dump(document, Dumper=get_dumper(use_annotations=True), default_flow_style=False),
                        "# leading\nvalue: 1 # inline\n",
                    )

    def test_yaml_comments_do_not_leak_between_documents(self):
        for first in "scalar", "null", "[]", "{}":
            with self.subTest(first=first):
                source = "# unattached\n" + first + " # unattached inline\n# trailing\n---\n# second\nkey: value\n"
                self.assertEqual(self.run_yq(source, ["-Y", "."]), "---\n" + first + "\n---\n# second\nkey: value\n")

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

        with tempfile.NamedTemporaryFile() as tf:
            tf.write(b'# top\nversion = "1.0.0" # keep\n')
            tf.seek(0)
            self.run_yq("", ["-i", "-T", '.version="1.0.1"', tf.name], input_format="toml")
            self.assertEqual(tf.read(), b'# top\nversion = "1.0.1" # keep\n')

    def test_explicit_doc_markers(self):
        test_doc = os.path.join(os.path.dirname(__file__), "doc.yml")
        self.assertTrue(self.run_yq("", ["-y", ".", test_doc]).startswith("---\nyaml_struct"))
        self.assertTrue(self.run_yq("", ["-y", "--explicit-start", ".", test_doc]).startswith("---"))
        self.assertTrue(self.run_yq("", ["-y", "--explicit-end", ".", test_doc]).endswith("...\n"))

    def test_xq(self):
        self.assertEqual(self.run_yq("<foo/>", ["."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["--xml-item-depth=2", "."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["--xml-dtd", "."], input_format="xml"), "")
        self.assertEqual(self.run_yq("<foo/>", ["-x", ".foo.x=1"], input_format="xml"), "<foo>\n  <x>1</x>\n</foo>\n")
        self.assertEqual(self.run_yq("<foo/>", ["-x", "."], input_format="xml"), "<foo></foo>\n")
        self.assertEqual(
            self.run_yq("<foo/>", ["-x", "--xml-short-empty-elements", "."], input_format="xml"), "<foo/>\n"
        )
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
            tf.seek(0)
            tf2.seek(0)
            self.assertEqual(
                self.run_yq(
                    "",
                    ["-x", "--xml-short-empty-elements", ".a", self.fd_path(tf), self.fd_path(tf2)],
                    input_format="xml",
                ),
                "<b/>\n<c/>\n",
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

    def test_tomlq_roundtrip(self):
        toml_doc = (
            "# top\n"
            "a = 1_000 # a\n"
            "b = 'old' # b\n"
            "arr = [1,  2, 3] # arr\n"
            'inline = { x = 1,  y = "z" } # inline\n'
            "\n"
            "[foo] # table\n"
            "bar = 2 # bar\n"
            "baz = 'x'\n"
        )
        self.assertEqual(self.run_yq(toml_doc, ["-T", "."], input_format="toml"), toml_doc)
        self.assertEqual(
            self.run_yq(toml_doc, ["-T", '.a=2000 | .b="new" | .foo.bar=3'], input_format="toml"),
            "# top\n"
            "a = 2000 # a\n"
            "b = 'new' # b\n"
            "arr = [1,  2, 3] # arr\n"
            'inline = { x = 1,  y = "z" } # inline\n'
            "\n"
            "[foo] # table\n"
            "bar = 3 # bar\n"
            "baz = 'x'\n",
        )
        self.assertEqual(
            self.run_yq(toml_doc, ["-T", '.arr[1]=9 | .inline.y="zz"'], input_format="toml"),
            "# top\n"
            "a = 1_000 # a\n"
            "b = 'old' # b\n"
            "arr = [1,  9, 3] # arr\n"
            'inline = { x = 1,  y = "zz" } # inline\n'
            "\n"
            "[foo] # table\n"
            "bar = 2 # bar\n"
            "baz = 'x'\n",
        )
        self.assertEqual(self.run_yq(toml_doc, ["-T", ".foo"], input_format="toml"), "bar = 2 # bar\nbaz = 'x'\n")

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

    def test_yaml_1_1_output_quotes(self):
        self.assertEqual(self.run_yq("on: -012345", ["-y", "."]), "'on': -12345\n")
        self.assertEqual(self.run_yq("on: '0900'", ["-y", "."]), "'on': '0900'\n")
        self.assertEqual(self.run_yq("a: abc\nb: cba\n", ["-y", '.a="23695230e640"']), "a: '23695230e640'\nb: cba\n")

        numeric_strings = [
            "0",
            "7",
            "08",
            "+9",
            "-9",
            "0o10",
            "0x10",
            "1.0",
            "1.0e10",
            "1e10",
            "1e+10",
            "1e-10",
            "23695230e640",
            ".5",
            ".inf",
            ".nan",
        ]
        yaml_doc = "".join(f"- '{value}'\n" for value in numeric_strings)
        self.assertEqual(self.run_yq(yaml_doc, ["-y", "."]), yaml_doc)

    def test_yaml_1_2_leading_zero_integers(self):
        self.assertEqual(self.run_yq("on: -012345", ["-y", "--yml-out-ver=1.2", "."]), "on: -12345\n")

        literals = []
        expected_values = []
        for sign in "", "+", "-":
            for width in 1, 2, 3:
                for value in range(10):
                    literals.append("{}{:0{}d}".format(sign, value, width))
                    expected_values.append(-value if sign == "-" else value)
        yaml_doc = "".join(f"- {literal}\n" for literal in literals)
        expected = "".join(f"- {value}\n" for value in expected_values)
        self.assertEqual(self.run_yq(yaml_doc, ["-y", "--yml-out-ver=1.2", "."]), expected)

        self.assertEqual(self.run_yq("octal: 0o10", ["-y", "--yml-out-ver=1.2", "."]), "octal: 8\n")
        self.assertEqual(self.run_yq("'08'", ["-y", "--yml-out-ver=1.2", "."]), "'08'\n")


if __name__ == "__main__":
    unittest.main()
