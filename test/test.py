#!/usr/bin/env python

import io
import os
import platform
import subprocess
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from yq import cli, yq

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
    loader = yaml.SafeLoader

    @classmethod
    def setUpClass(cls):
        from unittest import mock

        patch = mock.patch("yq.loader.default_loader", cls.loader)
        cls.addClassCleanup(patch.stop)
        patch.start()

    def python_command(self, script, *args):
        # Subprocesses need the same loader as calls made in this process.
        setup = f"import yaml, yq.loader; yq.loader.default_loader = yaml.{self.loader.__name__}\n"
        return [sys.executable, "-c", setup + script, *args]

    def yq_command(self, *args):
        return self.python_command("import runpy; runpy.run_module('yq', run_name='__main__')", *args)

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
            "yq: Error reading YAML input (<file>): ScannerError: while scanning for the next token\nfound character '%' that "
            'cannot start any token\n  in "<file>", line 1, column 3.'
        )
        err2 = (
            "yq: Error reading YAML input (<file>): ScannerError: while scanning for the next token\nfound character that "
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

    def test_from_file_option_positions(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            query, first, second = [os.path.join(directory, name) for name in ("filter.jq", "first.yml", "second.yml")]
            for path, text in [(query, ".a"), (first, "a: 1\n"), (second, "a: 2\n")]:
                with open(path, "w") as stream:
                    stream.write(text)
            arguments = [["-fc", query, first, second], ["-cf", query, first, second]]
            for flag in "-f", "--from-file":
                arguments.extend(
                    [
                        [flag, "-c", query, first, second],
                        [query, flag, first, second],
                        [flag, query, first, "-c", second],
                    ]
                )
            for args in arguments:
                with self.subTest(args=args):
                    self.assertEqual(self.run_yq("", ["-y", *args]), "1\n---\n2\n...\n")

            tty_input = mock.Mock()
            tty_input.isatty.return_value = True
            self.assertEqual(self.run_yq(tty_input, ["-y", "-nf", query]), "null\n...\n")

    @unittest.skipUnless(b"--library-path" in subprocess.check_output(["jq", "--help"]), "jq library-path option")
    def test_jq_library_path(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "input.yml")
            with open(os.path.join(directory, "example.jq"), "w") as stream:
                stream.write("def next_value(n): n + 1;")
            with open(source, "w") as stream:
                stream.write("a: 41\n")
            query = 'include "example"; next_value(.a)'
            for args in [
                ["--library-path", directory, query, source],
                [query, "--library-path", directory, source],
                ["-L", directory, query, source],
            ]:
                with self.subTest(args=args):
                    self.assertEqual(self.run_yq("", ["-y", *args]), "42\n...\n")

    def test_jq_version_short_option_clusters(self):
        for flag in "-cV", "-Vc":
            with self.subTest(flag=flag):
                expected = subprocess.run(["jq", flag], input=b"", capture_output=True, check=True)
                result = subprocess.run(self.yq_command(flag), input=b"", capture_output=True, timeout=5, check=True)
                self.assertEqual(result.stdout, expected.stdout)
                self.assertEqual(result.stderr, b"")

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
        self.assertEqual(self.run_yq('{"a": 1}', ["-yCcC", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-CcCy", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-y", "-CS", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-y", "-CC", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-y", "-cC", "."]), "a: 1\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-x", "-cC", "."]), "<a>1</a>\n")
        self.assertEqual(self.run_yq('{"a": 1}', ["-C", "."]), "")
        self.assertEqual(self.run_yq('{"a": 1}', ["-Cc", "."]), "")

    def fd_path(self, fh):
        return f"/dev/fd/{fh.fileno()}"

    def test_jq_output_options_during_conversion(self):
        options = [
            ["-r"],
            ["--raw-output"],
            ["-j"],
            ["--join-output"],
            ["--raw-output0"],
            ["-CrjcS"],
            ["--color-output"],
            ["--tab"],
            ["--indent", "4"],
            ["--indent=4"],
            ["--seq"],
        ]
        source = '{"a":"123","b":"Unicode: α, newline:\\n"}'
        for mode in "-y", "-Y", "-x", "-t", "-T":
            expected = self.run_yq(source, [mode, "., ."])
            for flags in options:
                with self.subTest(mode=mode, flags=flags):
                    self.assertEqual(self.run_yq(source, [mode, *flags, "., ."]), expected)

        import yaml

        for flag in "-r", "-j", "--raw-output0":
            result = self.run_yq("{}", ["-y", flag, '"123",123,"null",null,"a\\u0000b"'])
            self.assertEqual(list(yaml.safe_load_all(result)), ["123", 123, "null", None, "a\x00b"])

    def test_jq_output_options_passthrough(self):
        source = b'{"a":1,"s":"hello"}\n'
        for flags in (
            ["-r"],
            ["--raw-output"],
            ["-j"],
            ["--join-output"],
            ["-Crj"],
            ["--tab"],
            ["--indent", "4"],
            ["--indent", "4", "-c"],
            ["-c", "--indent", "4"],
            ["--tab", "-c"],
            ["-c", "--tab"],
            ["--indent", "4", "-c", "--indent", "1"],
        ):
            with self.subTest(flags=flags):
                query = ".s, ."
                expected = subprocess.run(["jq", *flags, query], input=source, capture_output=True, check=True)
                result = subprocess.run(
                    self.yq_command(*flags, query),
                    input=source,
                    capture_output=True,
                    timeout=5,
                    check=True,
                )
                self.assertEqual(result.stdout, expected.stdout)
                self.assertEqual(result.stderr, b"")

    def test_jq_option_operands_are_preserved(self):
        import json
        from unittest import mock

        from yq.parser import get_parser

        for value in "--raw-output", "--indent", "-Crj", "--seq":
            result = self.run_yq("{}", ["-y", "--argjson", "value", json.dumps(value), "{value:$value}"])
            self.assertEqual(result, f"value: {value}\n")
        self.assertEqual(self.run_yq("{}", ["-y", "-1 | tostring"]), "'-1'\n")

        parser = get_parser("yq", "")
        args, remaining = parser.parse_known_intermixed_args(
            ["-rLdirectoryCrj", "-jf", "filterCrj.jq", "--indent", "4", "--argjson", "value", '"--raw-output"', "."]
        )
        self.assertEqual(remaining, [])
        self.assertEqual(args.jq_filter, "filterCrj.jq")
        self.assertEqual(args.input_streams, ["."])
        self.assertEqual(
            args.jq_options,
            [
                ("-r", []),
                ("-L", ["directoryCrj"]),
                ("-j", []),
                ("-f", []),
                ("--indent", ["4"]),
                ("--argjson", ["value", '"--raw-output"']),
            ],
        )

        args = ["--argjson", "value", '"--raw-output"', "-rjCy", "{value:$value}"]
        with mock.patch("yq.subprocess.Popen", wraps=subprocess.Popen) as popen:
            self.assertEqual(self.run_yq("{}", args), "value: --raw-output\n")
            self.assertEqual(popen.call_count, 1)
        # Direct jq output receives the original arguments without injected
        # formatting options.
        args = ["--indent", "4", "-c", "--arg", "value", "-Crj", "empty"]
        with mock.patch("yq.subprocess.Popen", wraps=subprocess.Popen) as popen:
            with self.assertRaises(SystemExit):
                yq(input_streams=[io.StringIO(json.dumps({}))], jq_args=args)
            self.assertEqual(popen.call_args.args[0], ["jq", *args])

    def test_json_pull_parsing(self):
        import json

        from yq.stream_wrappers import JSONInputStreamWrapper

        values = [{"text": 'понедельник\nquoted "text"\x00'}, [], None, True, False, -1.25e30, 12345678901234567890]

        class ShortReads(io.BytesIO):
            def readinto(self, buffer):
                return super().readinto(memoryview(buffer)[:17])

        data = "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values).encode()
        source = io.BufferedReader(ShortReads(data))
        self.assertEqual(list(JSONInputStreamWrapper(source, json.JSONDecoder())), values)
        for source in '{"value":', '{"value": 1}\ninvalid', '"unterminated', "[1,\n2", "{} []\n", "123":
            with self.subTest(source=source), self.assertRaises(json.JSONDecodeError):
                list(JSONInputStreamWrapper(io.BufferedReader(io.BytesIO(source.encode())), json.JSONDecoder()))

    def test_json_buffered_lookahead(self):
        import json

        from yq.stream_wrappers import JSONInputStreamWrapper

        first = b'{"a": "first"}\n'
        source = io.BytesIO(first + b'{"a": "' + b"x" * (128 * 1024) + b'"}\n')
        buffered = io.BufferedReader(source)
        docs = JSONInputStreamWrapper(buffered, json.JSONDecoder())
        self.assertEqual(next(docs), {"a": "first"})
        for _ in range(3):
            self.assertTrue(docs.has_next())
            self.assertEqual(buffered.tell(), len(first))
            self.assertLessEqual(source.tell(), io.DEFAULT_BUFFER_SIZE)
        self.assertEqual(next(docs), {"a": "x" * (128 * 1024)})
        self.assertFalse(docs.has_next())
        self.assertEqual(list(docs), [])

    def test_json_pull_parsing_decodes_each_record_once(self):
        import json
        from unittest import mock

        from yq.stream_wrappers import JSONInputStreamWrapper

        values = [{"nested": [{"escaped": 'braces } ] and " and \\', "n": n} for n in range(2000)]}, False, 1e-20]
        text = "".join(json.dumps(value) + "\n" for value in values)
        source = io.BufferedReader(io.BytesIO(text.encode()))
        decoder = json.JSONDecoder()
        with mock.patch.object(decoder, "raw_decode", wraps=decoder.raw_decode) as decode:
            self.assertEqual(list(JSONInputStreamWrapper(source, decoder)), values)
        self.assertEqual(decode.call_count, len(values))

        for tail in b"invalid\n", b"123", b'{"a":':
            with self.subTest(tail=tail):
                source = io.BufferedReader(io.BytesIO(b'{"a":1}\n' + tail))
                docs = JSONInputStreamWrapper(source, decoder)
                self.assertEqual(next(docs), {"a": 1})
                with self.assertRaises(json.JSONDecodeError):
                    next(docs)

    @unittest.skipUnless(os.name == "posix", "POSIX pipe readiness")
    def test_jq_formatting_options_before_input_eof(self):
        import select
        import time

        value = b"x" * 20000
        expected = b"---\na: " + value + b"\n"
        for options in ["--indent", "2"], ["--tab"], ["--raw-output0"], ["-rjC"]:
            with self.subTest(options=options), subprocess.Popen(
                self.yq_command("-y", *options, "."),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    process.stdin.write(b"---\na: " + value + b"\n...\n---\n")
                    process.stdin.flush()
                    result = b""
                    deadline = time.monotonic() + 5
                    while len(result) < len(expected):
                        timeout = deadline - time.monotonic()
                        self.assertGreater(timeout, 0, "Output waited for input EOF")
                        self.assertTrue(select.select([process.stdout], [], [], timeout)[0])
                        chunk = os.read(process.stdout.fileno(), len(expected) - len(result))
                        self.assertTrue(chunk, "Unexpected EOF")
                        result += chunk
                    self.assertEqual(result, expected)
                    stdout, stderr = process.communicate(b"a: final\n", timeout=5)
                    self.assertEqual((stdout, stderr, process.returncode), (b"---\na: final\n", b"", 0))
                finally:
                    if process.poll() is None:
                        process.kill()

    def test_completed_yaml_survives_jq_error(self):
        result = subprocess.run(
            self.yq_command("-y", '{a:"first"}, error("later failure")'),
            input=b"---\n{}\n",
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 5)
        self.assertEqual(result.stdout, b"---\na: first\n")
        self.assertIn(b"later failure", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    @unittest.skipUnless(os.name == "posix", "POSIX cancellable pipe input")
    def test_jq_early_exit_before_input_eof(self):
        for options in ["-y"], ["-Y"], ["-y", "--no-expand-aliases"], ["-Y", "--no-expand-aliases"]:
            with self.subTest(options=options), subprocess.Popen(
                self.yq_command(*options, "-n", "first(inputs)", "-"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    process.stdin.write(b"a: 1\n...\n")
                    process.stdin.flush()
                    # Keep stdin open until yq exits, including its input worker.
                    self.assertEqual(process.wait(timeout=5), 0)
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual((stdout, stderr), (b"a: 1\n", b""))
                finally:
                    if process.poll() is None:
                        process.kill()

    def test_yaml_reader_split_characters(self):
        import codecs

        from yq.loader import get_loader

        class ShortReads(io.BytesIO):
            def read(self, size=-1):
                return super().read(min(size, 1))

        source = "value: café ☃ 😀\n...\n---\nvalue: final\n"
        encodings = [("utf-8", b""), ("utf-16-le", codecs.BOM_UTF16_LE), ("utf-16-be", codecs.BOM_UTF16_BE)]
        for annotations in False, True:
            loader = get_loader(use_annotations=annotations)
            for encoding, prefix in encodings:
                with self.subTest(annotations=annotations, encoding=encoding):
                    stream = ShortReads(prefix + source.encode(encoding))
                    self.assertEqual(
                        list(yaml.load_all(stream, Loader=loader)), [{"value": "café ☃ 😀"}, {"value": "final"}]
                    )
            for invalid in b"value: \xff", b"value: \xe2\x98", b"value: \x00":
                with self.subTest(annotations=annotations, source=invalid), self.assertRaises(yaml.reader.ReaderError):
                    list(yaml.load_all(ShortReads(invalid), Loader=loader))

    @unittest.skipUnless(os.name == "posix", "POSIX pipe readiness and signals")
    def test_generated_documents_before_nonterminating_query(self):
        import select
        import signal
        import time

        query = "{n:0}, (while(true; .) | empty)"
        with subprocess.Popen(
            self.yq_command("-y", "--null-input", query),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            try:
                expected = b"n: 0\n"
                result = b""
                deadline = time.monotonic() + 5
                while len(result) < len(expected):
                    timeout = deadline - time.monotonic()
                    self.assertGreater(timeout, 0, "Completed output waited for query termination")
                    self.assertTrue(select.select([process.stdout], [], [], timeout)[0])
                    chunk = os.read(process.stdout.fileno(), len(expected) - len(result))
                    self.assertTrue(chunk, "Unexpected EOF")
                    result += chunk
                self.assertEqual(result, expected)
                self.assertIsNone(process.poll())
                process.send_signal(signal.SIGINT)
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual((stdout, stderr, process.returncode), (b"", b"", 130))
            finally:
                if process.poll() is None:
                    process.kill()

    @unittest.skipUnless(os.name == "posix", "POSIX pipe readiness")
    def test_first_yaml_output_before_second_input(self):
        import select

        for source in "a: first\n", "---\na: first\n":
            script = (
                "import io, sys, yq\n"
                f"yq.yq(input_streams=[io.StringIO({source!r}), sys.stdin], "
                "output_format='yaml', jq_args=['.'])\n"
            )
            with self.subTest(source=source), subprocess.Popen(
                self.python_command(script),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], "First input was not printed")
                    self.assertEqual(os.read(process.stdout.fileno(), len(source)), source.encode())
                    stdout, stderr = process.communicate(b"a: second\n", timeout=5)
                    self.assertEqual((stdout, stderr, process.returncode), (b"---\na: second\n", b"", 0))
                finally:
                    if process.poll() is None:
                        process.kill()

    def test_completed_yaml_survives_invalid_next_input(self):
        result = subprocess.run(
            self.yq_command("-y", "."),
            input=b"---\na: first\n---\nbroken: [\n",
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"---\na: first\n")
        self.assertIn(b"Error reading YAML input", result.stderr)

    def test_output_flushed_before_next_document(self):
        import json
        from unittest import mock

        from yq.stream_wrappers import JSONInputStreamWrapper

        test = self
        first = b'{"a":"first"}\n'

        class Output(io.StringIO):
            flushed = ""

            def seek(self, *args):
                raise AssertionError("Output must not seek")

            def flush(self):
                self.flushed = self.getvalue()

        class Input(io.BufferedReader):
            def readline(self):
                if self.tell() == len(first):
                    test.assertEqual(output.flushed, expected)
                return super().readline()

            def seek(self, *args):
                raise AssertionError("Input must not seek")

        for mode, expected in [
            ("yaml", "a: first\n"),
            ("annotated_yaml", "a: first\n"),
            ("xml", "<a>first</a>\n"),
            ("toml", 'a = "first"\n'),
            ("annotated_toml", 'a = "first"\n'),
        ]:
            output = Output()
            docs = JSONInputStreamWrapper(Input(io.BytesIO(first + b'{"a":"second"}\n')), json.JSONDecoder())
            with self.subTest(mode=mode), mock.patch("yq.JSONInputStreamWrapper", return_value=docs):
                with self.assertRaises(SystemExit) as exit:
                    yq(input_streams=[io.StringIO("{}")], output_stream=output, output_format=mode, jq_args=["empty"])
                self.assertEqual(exit.exception.code, 0)

    def test_named_input_diagnostics(self):
        with tempfile.NamedTemporaryFile() as source:
            source.write(b"invalid: [\n")
            source.flush()
            for mode in "-y", "-Y":
                result = subprocess.run(
                    self.yq_command(mode, ".", source.name), capture_output=True, timeout=5, check=False
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(source.name.encode(), result.stderr)
                self.assertIn(b"Error reading YAML input", result.stderr)
                self.assertNotIn(b'"<file>"', result.stderr)

    def test_jq_failure_with_open_stdin(self):
        for options in [], ["-y"]:
            with self.subTest(options=options), subprocess.Popen(
                self.yq_command(*options, "["),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    self.assertEqual(process.wait(timeout=5), 3)
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual(stdout, b"")
                    self.assertIn(b"jq: 1 compile error", stderr)
                finally:
                    if process.poll() is None:
                        process.kill()

    def test_closed_output_pipe(self):
        with subprocess.Popen(
            self.yq_command("-y", "-n", "range(0;100000)"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            try:
                self.assertEqual(process.stdout.readline(), b"0\n")
                process.stdout.close()
                process.stdout = None
                _, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 141)
                self.assertEqual(stderr, b"")
            finally:
                if process.poll() is None:
                    process.kill()

    def test_cli_unexpected_errors_have_no_tracebacks(self):
        for error in ["ValueError('unexpected failure')", "BaseException('unexpected failure')"]:
            script = (
                "from unittest import mock\n"
                "from yq import cli\n"
                f"with mock.patch('yq.parse_cli_args_and_run_yq', side_effect={error}):\n"
                "    cli()\n"
            )
            result = subprocess.run(self.python_command(script), capture_output=True, timeout=5, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"yq: ", result.stderr)
            self.assertIn(b"unexpected failure", result.stderr)
            self.assertNotIn(b"Traceback", result.stderr)
            self.assertNotIn(b'File "', result.stderr)

    def test_cli_thread_and_shutdown_errors_have_no_tracebacks(self):
        script = """
import atexit
import threading
from unittest import mock
from yq import cli

def fail():
    raise RuntimeError("injected failure")

def run(*args):
    thread = threading.Thread(target=fail)
    thread.start()
    thread.join()
    atexit.register(fail)

with mock.patch("yq.parse_cli_args_and_run_yq", run):
    cli()
"""
        result = subprocess.run(self.python_command(script), capture_output=True, timeout=5, check=False)
        self.assertIn(b"injected failure", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(b'File "', result.stderr)

    def test_input_pipe_close_error_is_reported(self):
        from unittest import mock

        popen = subprocess.Popen

        def start(*args, **kwargs):
            process = popen(*args, **kwargs)
            close = process.stdin.close

            def fail():
                close()
                raise OSError("input pipe close failed")

            process.stdin.close = fail
            return process

        with mock.patch("yq.subprocess.Popen", start), self.assertRaisesRegex(SystemExit, "input pipe close failed"):
            yq(
                input_streams=[io.StringIO("a: value\n")],
                output_stream=io.StringIO(),
                output_format="yaml",
                jq_args=["."],
            )

    @unittest.skipUnless(os.name == "posix", "POSIX FIFOs")
    def test_live_fifo_documents_and_lazy_open(self):
        import errno
        import select
        import time

        def open_writer(path):
            deadline = time.monotonic() + 5
            while True:
                try:
                    return open(os.open(path, os.O_WRONLY | os.O_NONBLOCK), "wb", buffering=0)
                except OSError as error:
                    if error.errno != errno.ENXIO or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)

        def read_output(expected):
            result = b""
            deadline = time.monotonic() + 5
            while len(result) < len(expected):
                self.assertGreater(deadline - time.monotonic(), 0, "Document was not flushed")
                self.assertTrue(select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))[0])
                chunk = os.read(process.stdout.fileno(), len(expected) - len(result))
                self.assertTrue(chunk, "Unexpected EOF")
                result += chunk
            self.assertEqual(result, expected)

        with tempfile.TemporaryDirectory() as directory:
            first, second = [os.path.join(directory, name) for name in ("first", "second")]
            os.mkfifo(first)
            os.mkfifo(second)
            with subprocess.Popen(
                self.yq_command("-y", ".", first, second),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    with open_writer(first) as writer:
                        for text in (b"---\na: first\n...\n---\n", b"a: second\n...\n---\n"):
                            writer.write(text)
                            expected = b"---\na: first\n" if b"first" in text else b"---\na: second\n"
                            read_output(expected)
                        writer.write(b"a: third\n")
                    read_output(b"---\na: third\n")
                    with open_writer(second) as writer:
                        writer.write(b"a: last\n")
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual((stdout, stderr, process.returncode), (b"---\na: last\n", b"", 0))
                finally:
                    if process.poll() is None:
                        process.kill()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process state checks")
    def test_interrupt_reaps_jq(self):
        import signal
        import time

        # Cover idle input, waiting on jq, and a full stdout pipe. Only signal
        # yq: it must clean up its child without relying on group signalling.
        for arguments, state in [
            (["-y", "."], "pipe_read"),
            (["-y", "-n", "while(true; .) | empty"], "pipe_read"),
            (["-y", "-n", 'range(0;1000000) | {a:("x" * 4096)}'], "pipe_write"),
        ]:
            with self.subTest(arguments=arguments), subprocess.Popen(
                self.yq_command(*arguments),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ) as process:
                try:
                    deadline = time.monotonic() + 5
                    child = None
                    while time.monotonic() < deadline:
                        with open(f"/proc/{process.pid}/task/{process.pid}/children") as stream:
                            children = stream.read().split()
                        with open(f"/proc/{process.pid}/wchan") as stream:
                            channel = stream.read()
                        if children and state in channel:
                            child = int(children[0])
                            break
                        time.sleep(0.01)
                    self.assertIsNotNone(child, "yq did not reach the expected blocking operation")
                    os.kill(process.pid, signal.SIGINT)
                    _, stderr = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 130)
                    self.assertEqual(stderr, b"")
                    with self.assertRaises(ProcessLookupError):
                        os.kill(child, 0)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_in_place_write_failure_stops_writing(self):
        import errno
        from unittest import mock

        from yq import edit_in_place

        original = b"a: original\r\n# preserve comment and trailing bytes\r\n"
        replacement = b"a: updated\n"
        for failure in [OSError(errno.ENOSPC, "No space left on device"), KeyboardInterrupt(), RuntimeError("failure")]:
            with self.subTest(failure=type(failure).__name__), tempfile.NamedTemporaryFile() as source:
                source.write(original)
                source.flush()

                def failing_write(stream, data, failure=failure):
                    stream.write(data[:6])
                    raise failure

                def render(**kwargs):
                    kwargs["output_stream"].write(replacement.decode())

                with mock.patch("yq.yq", render), mock.patch(
                    "yq.write_all", side_effect=failing_write
                ) as write, self.assertRaises(type(failure)) as raised:
                    edit_in_place(source.name, {})
                source.seek(0)
                self.assertEqual(source.read(), replacement[:6] + original[6:])
                write.assert_called_once()
                if isinstance(failure, OSError):
                    self.assertIn(source.name, str(raised.exception))
                    self.assertIn("the file may be incomplete", str(raised.exception))

    def test_in_place_sync_failure_stops_writing(self):
        from unittest import mock

        from yq import edit_in_place, write_all

        with tempfile.NamedTemporaryFile() as source:
            source.write(b"a: original contents with a longer tail\n")
            source.flush()

            def render(**kwargs):
                kwargs["output_stream"].write("a: updated\n")

            with mock.patch("yq.yq", render), mock.patch("yq.write_all", wraps=write_all) as write, mock.patch(
                "yq.os.fsync", side_effect=OSError("sync failed")
            ), self.assertRaisesRegex(OSError, "sync failed.*the file may be incomplete"):
                edit_in_place(source.name, {})
            write.assert_called_once()
            source.seek(0)
            self.assertEqual(source.read(), b"a: updated\n")

    @unittest.skipUnless(os.name == "posix", "POSIX file replacement")
    def test_in_place_retains_original_filehandle(self):
        from unittest import mock

        from yq import edit_in_place

        with tempfile.TemporaryDirectory() as directory:
            path, moved = [os.path.join(directory, name) for name in ("input.yml", "moved.yml")]
            with open(path, "w") as stream:
                stream.write("a: original\n")

            def render(**kwargs):
                os.rename(path, moved)
                with open(path, "w") as stream:
                    stream.write("a: swapped\n")
                kwargs["output_stream"].write("a: updated\n")

            with mock.patch("yq.yq", render):
                edit_in_place(path, {})
            with open(path) as stream:
                self.assertEqual(stream.read(), "a: swapped\n")
            with open(moved) as stream:
                self.assertEqual(stream.read(), "a: updated\n")

    def test_yaml_output_before_reading_second_result(self):
        from unittest import mock

        from yq.stream_wrappers import JSONInputStreamWrapper

        test = self

        class GatedInput:
            def __init__(self, stream, output):
                self.stream = stream
                self.output = output
                self.lines = 0

            def peek(self, size):
                return self.stream.peek(size)

            def readline(self):
                if self.lines:
                    test.assertTrue(self.output.getvalue().startswith("a: first"))
                self.lines += 1
                return self.stream.readline()

            def close(self):
                self.stream.close()

        source = "a: first document\n---\na: second document\n"
        for mode in "yaml", "annotated_yaml":
            output = io.StringIO()

            def parse_output(stream, decoder, output=output):
                return JSONInputStreamWrapper(GatedInput(stream, output), decoder)

            with self.subTest(mode=mode), mock.patch("yq.JSONInputStreamWrapper", parse_output):
                with self.assertRaises(SystemExit) as exit:
                    yq(input_streams=[io.StringIO(source)], output_stream=output, output_format=mode, jq_args=["."])
                self.assertEqual(exit.exception.code, 0)
                self.assertEqual(output.getvalue(), source)

    def test_no_temporary_files(self):
        from contextlib import ExitStack
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            first, second = [os.path.join(directory, name) for name in ("first.yml", "second.yml")]
            for path, content in [(first, "a: first\n---\na: second\n"), (second, "---\na: third\n")]:
                with open(path, "w") as stream:
                    stream.write(content)
            for name in "TemporaryFile", "NamedTemporaryFile", "SpooledTemporaryFile", "TemporaryDirectory", "mkstemp":
                stack.enter_context(mock.patch("tempfile." + name, side_effect=AssertionError("Temporary file used")))
            self.assertEqual(
                self.run_yq("", ["-y", ".", first, second]),
                "a: first\n---\na: second\n---\na: third\n",
            )
            self.assertEqual(self.run_yq("---\na: first\n---\n# body", ["-YF", "."]), "---\na: first\n---\n# body")
            self.assertEqual(self.run_yq("<a>first</a>", ["-x", "."], input_format="xml"), "<a>first</a>\n")
            for mode in "-t", "-T":
                self.assertEqual(self.run_yq("a = 1\n", [mode, "."], input_format="toml"), "a = 1\n")
            self.run_yq("", ["-iy", '.a += " updated"', first, second])
            with open(first) as stream:
                saved = stream.read()
            self.assertEqual(saved, "a: first updated\n---\na: second updated\n")
            with open(second) as stream:
                self.assertEqual(stream.read(), "---\na: third updated\n")
            self.run_yq("", ["-iy", "[", first], expect_exit_codes={3})
            with open(first) as stream:
                self.assertEqual(stream.read(), saved)
            self.run_yq(
                "",
                ["-iy", 'if .a == "second updated" then error("failed") else . end', first],
                expect_exit_codes={5},
            )
            with open(first) as stream:
                self.assertEqual(stream.read(), saved)

    def test_yaml_document_lifetimes(self):
        import gc
        import weakref
        from unittest import mock

        from yq.loader import get_loader

        test = self
        for output_args in [], ["-y"], ["-Y"]:
            document_refs, node_refs = [], []

            class Document(dict):
                pass

            def tracked_loader(document_refs=document_refs, node_refs=node_refs, **kwargs):
                class Loader(get_loader(**kwargs)):
                    def get_node(self):
                        gc.collect()
                        test.assertTrue(all(ref() is None for ref in document_refs))
                        test.assertTrue(all(ref() is None for ref in node_refs))
                        node = super().get_node()
                        node_refs.append(weakref.ref(node))
                        return node

                    def construct_document(self, node):
                        document = Document(super().construct_document(node))
                        document_refs.append(weakref.ref(document))
                        return document

                return Loader

            with self.subTest(output_args=output_args), mock.patch("yq.get_loader", tracked_loader):
                self.run_yq("# first\na: 1\n---\na: 2\n---\na: 3\n", [*output_args, "."])
                self.assertEqual(len(document_refs), 3)
                gc.collect()
                self.assertTrue(all(ref() is None for ref in document_refs + node_refs))

    def test_separate_document_lifetimes(self):
        import gc
        import weakref
        from unittest import mock

        import tomlkit
        import xmltodict

        from yq import get_toml_loader

        class Document(dict):
            pass

        cases = [
            ("xml", "<a>1</a>", "xmltodict.parse", xmltodict.parse, [[], ["-x"]]),
            ("toml", "a = 1", "tomlkit.load", tomlkit.load, [["-t"], ["-T"]]),
            ("toml", "a = 1", "yq.get_toml_loader", get_toml_loader(), [[]]),
        ]
        for input_format, source, target, load, modes in cases:
            for mode in modes:
                refs = []

                wrap = input_format == "xml" or target == "yq.get_toml_loader"

                def tracked_load(*args, load=load, refs=refs, wrap=wrap, **kwargs):
                    gc.collect()
                    self.assertTrue(all(ref() is None for ref in refs))
                    document = load(*args, **kwargs)
                    if wrap:
                        document = Document(document)
                    refs.append(weakref.ref(document))
                    return document

                replacement = (lambda: tracked_load) if target == "yq.get_toml_loader" else tracked_load
                formats = {"-x": "xml", "-t": "toml", "-T": "annotated_toml"}
                with self.subTest(input_format=input_format, mode=mode), mock.patch(target, replacement):
                    with self.assertRaises(SystemExit) as exit:
                        yq(
                            input_streams=[io.StringIO(source), io.StringIO(source)],
                            output_stream=io.StringIO(),
                            input_format=input_format,
                            output_format=formats[mode[0]] if mode else "json",
                            jq_args=["."],
                        )
                    self.assertEqual(exit.exception.code, 0)
                    self.assertEqual(len(refs), 2)
                    gc.collect()
                    self.assertTrue(all(ref() is None for ref in refs))

    def test_output_document_lifetimes(self):
        import gc
        import json
        import weakref
        from unittest import mock

        decoder_class = json.JSONDecoder

        from yq.dumper import get_dumper

        class Document(dict):
            pass

        def tracked_dumper(**kwargs):
            dumper = get_dumper(**kwargs)
            dumper.add_representer(Document, dumper.yaml_representers[dict])
            return dumper

        for mode in "-y", "-Y", "-x", "-t", "-T":
            refs = []

            def document_hook(value, refs=refs):
                gc.collect()
                self.assertTrue(all(ref() is None for ref in refs), "The previous jq result is still referenced")
                document = Document(value)
                refs.append(weakref.ref(document))
                return document

            with self.subTest(mode=mode), mock.patch(
                "yq.json.JSONDecoder", lambda: decoder_class(object_hook=document_hook)
            ), mock.patch("yq.get_dumper", tracked_dumper):
                self.run_yq("a: 1\n---\na: 2\n---\na: 3\n", [mode, "."])
                self.assertEqual(len(refs), 3)
                gc.collect()
                self.assertTrue(all(ref() is None for ref in refs))

    def test_streaming_uses_one_jq(self):
        from unittest import mock

        for input_format, document in [("yaml", "a: 1\n"), ("xml", "<a>1</a>"), ("toml", "a = 1\n")]:
            with self.subTest(input_format=input_format), mock.patch(
                "yq.subprocess.Popen", wraps=subprocess.Popen
            ) as popen:
                output = io.StringIO()
                with self.assertRaises(SystemExit) as exit:
                    yq(
                        input_streams=[io.StringIO(document) for _ in range(3)],
                        output_stream=output,
                        input_format=input_format,
                        output_format="yaml",
                        jq_args=["--slurp", "{total: (map(.a | tonumber) | add)}"],
                    )
                self.assertEqual(exit.exception.code, 0)
                self.assertEqual(output.getvalue(), "total: 3\n")
                popen.assert_called_once()

    def test_yaml_nonseekable_streaming(self):
        import threading

        test = self
        output_seen = threading.Event()

        class Output(io.StringIO):
            def write(self, text):
                output_seen.set()
                return super().write(text)

        class Input(io.StringIO):
            def seek(self, *args):
                raise AssertionError("YAML input must not be rewound")

            def read(self, size=-1):
                test.assertGreater(size, 0)
                test.assertLessEqual(size, 64 * 1024)
                if self.tell() > 128 * 1024:
                    test.assertTrue(output_seen.wait(5), "No output until the whole YAML stream was read")
                return super().read(size)

        for mode in "yaml", "annotated_yaml":
            for prefix in "", "# comment\n---\n", "%YAML 1.1\n---\n":
                with self.subTest(mode=mode, prefix=prefix):
                    output_seen.clear()
                    source = prefix + "a: " + "x" * 16384 + "\n"
                    source += ("---\na: " + "x" * 16384 + "\n") * 20
                    output = Output()
                    with self.assertRaises(SystemExit) as exit:
                        yq(input_streams=[Input(source)], output_stream=output, output_format=mode, jq_args=["."])
                    self.assertEqual(exit.exception.code, 0)
                    self.assertEqual(output.getvalue().count("---\n"), 21 if prefix else 20)

    def test_streaming_pipe_cleanup(self):
        source = ("---\na: " + "x" * (128 * 1024) + "\n") * 4
        cases = [
            (["-y", "."], 0),
            (["-y", "--indent", "4", "."], 0),
            (["-y", "-n", "first(inputs)"], 0),
            (["-y", "-n", "halt"], 0),
            (["-y", "-n", "halt_error(7)"], 7),
            (["-y", "["], 3),
            (["-x", ".a"], 1),
        ]
        for args, code in cases:
            with self.subTest(args=args):
                result = subprocess.run(
                    self.yq_command(*args),
                    input=source.encode(),
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(result.returncode, code, result.stderr.decode())
        result = subprocess.run(
            self.yq_command("-y", "."),
            input=(source + "---\ninvalid: [").encode(),
            capture_output=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"ParserError", result.stderr)

    def test_multidocs(self):
        self.assertEqual(self.run_yq("---\na: b\n---\nc: d", ["-y", "."]), "---\na: b\n---\nc: d\n")
        with tempfile.TemporaryFile() as tf, tempfile.TemporaryFile() as tf2:
            tf.write(b'{"a": "b"}')
            tf.seek(0)
            tf2.write(b'{"a": 1}')
            tf2.seek(0)
            self.assertEqual(self.run_yq("", ["-y", ".a", self.fd_path(tf), self.fd_path(tf2)]), "b\n---\n1\n...\n")

    def test_streaming_yaml_end_markers(self):
        source = "text: |\n  ...\n---\ntext: |\n  ...\n"
        self.assertEqual(self.run_yq(source, ["-Y", "."]), source)
        self.assertEqual(
            self.run_yq(source, ["-Y", "--explicit-end", "."]),
            "text: |\n  ...\n...\n---\ntext: |\n  ...\n...\n",
        )
        source = "---\ntext: |\n  ...\n---\n# body\n"
        self.assertEqual(self.run_yq(source, ["-YF", "."]), source)

    def test_leading_document_marker(self):
        for mode in "-y", "-Y":
            with self.subTest(mode=mode):
                self.assertEqual(self.run_yq("a: b\n", [mode, "."]), "a: b\n")
                self.assertEqual(self.run_yq("---\na: b\n", [mode, "."]), "---\na: b\n")
                self.assertEqual(self.run_yq("%YAML 1.1\n---\na: b\n", [mode, "."]), "---\na: b\n")
                self.assertTrue(self.run_yq("# header\n---\na: b\n", [mode, "."]).startswith("---\n"))
                self.assertEqual(self.run_yq("a: b\n---\nc: d\n", [mode, "."]), "a: b\n---\nc: d\n")
                self.assertEqual(self.run_yq("a: b\n", [mode, "., ."]), "a: b\n---\na: b\n")
                self.assertEqual(self.run_yq("a: b\n---\nc: d\n", [mode, "select(.a)"]), "a: b\n")
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
            self.yq_command("-F", "-r", ".title"),
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
                "yq: Error converting jq output to ANNOTATED_YAML: ValueError: --yaml-frontmatter requires the jq filter "
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
                self.assertEqual(self.run_yq(source, ["-Y", "."]), first + "\n---\n# second\nkey: value\n")

    def test_in_place_yaml(self):
        with tempfile.NamedTemporaryFile() as tf, tempfile.NamedTemporaryFile() as tf2:
            tf.write(b"- foo\n- bar\n")
            tf.seek(0)
            tf2.write(b"- foo\n- bar\n")
            tf2.seek(0)
            self.run_yq("", ["-i", "-y", ".[0]", tf.name, tf2.name])
            self.assertEqual(tf.read(), b"foo\n...\n")
            self.assertEqual(tf2.read(), b"foo\n...\n")

            self.run_yq("", ["-nyi", '{a: "replacement"}', tf.name])
            tf.seek(0)
            self.assertEqual(tf.read(), b"a: replacement\n")
            self.run_yq("", ["-nyi", '"foo"', tf.name])

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

    def test_yaml_merge_expansion_defense(self):
        # Each level collapses to {k: v}, but flattening the merges copies 4**level pairs.
        # Keep the payload small and lower the limit so a regression cannot exhaust memory.
        for merge_sequence in True, False:
            source = "a0: &a0\n  k: v\n"
            for level in range(1, 7):
                source += f"a{level}: &a{level}\n"
                if merge_sequence:
                    aliases = ", ".join([f"*a{level - 1}"] * 4)
                    source += f"  <<: [{aliases}]\n"
                else:
                    source += f"  <<: *a{level - 1}\n" * 4
            for output_args in [], ["-y"], ["-Y"]:
                with self.subTest(merge_sequence=merge_sequence, output_args=output_args):
                    self.run_yq(
                        source,
                        [*output_args, "--max-expansion-factor", "4", "."],
                        expect_exit_codes={"yq: Error: detected unsafe YAML entity expansion"},
                    )
            # A larger configured budget allows the same input, and resets for each document.
            self.assertEqual(
                self.run_yq("---\n".join([source] * 3), ["-y", "--max-expansion-factor", "32", ".a6"]),
                "k: v\n" + "---\nk: v\n" * 2,
            )

    def test_yaml_merge_expansion_rejected_before_json(self):
        from unittest import mock

        import yaml

        from yq import load_yaml_docs
        from yq.loader import default_loader, get_loader

        source = "a: &a {k: v}\nb: {<<: [" + ", ".join(["*a"] * 4) + "]}\n"
        for base_loader in yaml.SafeLoader, default_loader:
            with self.subTest(loader=base_loader), mock.patch("yq.loader.default_loader", base_loader):
                loader_class = get_loader()
                jq = mock.Mock()
                out_stream = io.StringIO()
                # Set a tiny budget to exercise rejection before JSON encoding starts.
                with mock.patch("yq.JSONDateTimeEncoder") as encoder, self.assertRaisesRegex(
                    SystemExit, "^yq: Error: detected unsafe YAML entity expansion$"
                ):
                    load_yaml_docs(io.StringIO(source), out_stream, jq, loader_class, 0, sys.exit, "yq")
                encoder.assert_not_called()
                jq.kill.assert_called_once_with()
                self.assertEqual(out_stream.getvalue(), "")

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
        source = "a: &a {x: first, y: first}\nb: &b {x: second, z: second}\nresult:\n  <<: [*a, *b]\n  y: explicit\n"
        for output_arg in "-y", "-Y":
            with self.subTest(output_arg=output_arg):
                self.assertEqual(
                    self.run_yq(source, [output_arg, '.result == {x: "first", y: "explicit", z: "second"}']),
                    "true\n...\n",
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


if yaml.__with_libyaml__:

    class TestYqLibYaml(TestYq):
        loader = yaml.CSafeLoader


if __name__ == "__main__":
    unittest.main()
