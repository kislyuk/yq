Changes for v3.4.2 (2024-04-26)
===============================

Constrain setuptools_scm version

Changes for v3.4.1 (2024-04-17)
===============================

-  Add module entry points for xq and tomlq

Changes for v3.4.0 (2024-04-17)
===============================

-  yq -y: Induce quoting of string scalars that start with 08 and 09

Changes for v3.3.1 (2024-04-15)
===============================

Revert “Do not interpret characters that cannot be parsed in octal as
int (#176)”

Changes for v3.3.0 (2024-04-13)
===============================

-  tomlq: Use tomllib on Python 3.11 when not round-tripping

-  xq: Support in-place XML editing

-  Do not interpret characters that cannot be parsed in octal as int
   (#176)

Changes for v3.2.3 (2023-09-09)
===============================

-  test.py: use valid values for jsonargs. Fixes #172

-  Allow editing toml in place (#171)

-  Documentation improvements

Changes for v3.2.2 (2023-04-22)
===============================

-  Allow XML documents to be streamed with –xml-item-depth

Changes for v3.2.1 (2023-04-04)
===============================

-  Relax tomlkit dependency version range to preserve Python 3.6
   compatibility (#165)

Changes for v3.2.0 (2023-04-03)
===============================

-  Use tomlkit instead of toml

-  Add security policy

-  Documentation and release infrastructure improvements

Changes for v3.1.1 (2023-02-21)
===============================

-  Handle TOML datetimes. Fixes #160

-  Test and documentation improvements

Changes for v3.1.0 (2022-07-24)
===============================

-  Use configurable output grammar, compatible with YAML 1.1

Changes for v3.0.2 (2022-07-05)
===============================

-  Expand merge keys (https://yaml.org/type/merge.html). This is a YAML
   1.1 specific behavior, but will be accommodated in yq due to its
   widespread use and low likelihood of accidental invocation.

Changes for v3.0.1 (2022-07-04)
===============================

-  yq now uses the YAML 1.2 grammar when parsing and rendering YAML
   documents. This means bare literals like “on”, “no”, and “12:34:56”
   are interpreted as strings. (Fix interrupted release)

Changes for v3.0.0 (2022-07-04)
===============================

-  yq now uses the YAML 1.2 grammar when parsing and rendering YAML
   documents. This means bare literals like “on”, “no”, and “12:34:56”
   are interpreted as strings.

Changes for v2.14.0 (2022-02-20)
================================

-  Support binary and set tags. Fixes #140

Changes for v2.13.0 (2021-12-02)
================================

-  Armor against entity expansion attacks

-  Improve YAML loading performance by using CSafeLoader where available

-  Require PyYAML 5.3.1 or newer

-  Test and release infrastructure improvements

Changes for v2.12.2 (2021-06-13)
================================

-  Handle -n correctly

Changes for v2.12.1 (2021-06-13)
================================

-  Do not close fds on child process

Changes for v2.12.0 (2021-02-05)
================================

-  Add TOML support and the tomlq CLI utility to access it

-  Drop Python 2.7 support

Changes for v2.11.1 (2020-09-26)
================================

Parse correctly when empty string is passed as jq_filter

Changes for v2.11.0 (2020-09-03)
================================

-  Better handling of jq_filter and files arguments (#102)

-  Create **main**.py (#82)

Changes for v2.10.1 (2020-05-11)
================================

-  Add support for xmltodict force_list definition for xq CLI (#95)

-  Support explicit doc markers (#93)

-  Ensure proper ordering of help messages (#90)

Changes for v2.10.0 (2019-12-23)
================================

-  Add support for in-place editing (yq -yi)

-  Add argcomplete integration

-  Docs: Migrate from RTD to gh-pages

Changes for v2.9.2 (2019-11-04)
===============================

-  Fix interrupted release

Changes for v2.9.1 (2019-11-04)
===============================

-  Fix documentation build

Changes for v2.9.0 (2019-11-04)
===============================

-  Add -Y/–yaml-roundtrip for preserving YAML styles and tags

Changes for v2.8.1 (2019-10-28)
===============================

-  Filter out -C and separate commingled yq and jq short options

Changes for v2.8.0 (2019-10-25)
===============================

-  Set default block sequence indentation to 2 spaces, –indentless for 0

-  Make main body of yq callable as a library function

-  Test and release infrastructure updates

Changes for v2.7.2 (2019-01-09)
===============================

-  Support options introduced in jq 1.6. Fixes #46

-  xq: Re-raise if exception is unrecognized

Changes for v2.7.1 (2018-11-05)
===============================

-  xq: Introduce –xml-dtd and –xml-root. Fixes #37.

-  TOML support is optional and experimental

Changes for v2.7.0 (2018-08-04)
===============================

-  TOML support with the tq executable entry point.

-  Disallow argparse abbreviated options. Fixes #38 on Python 3.5+.

-  Now available in Homebrew as python-yq.

Changes for v2.6.0 (2018-04-28)
===============================

-  Packaging: Replace scripts with entry-points

-  Packaging: Package the license file

Changes for v2.5.0 (2018-04-02)
===============================

-  Parse unrecognized tags instead of dropping them. Fixes #23

Changes for v2.4.1 (2018-02-13)
===============================

-  Ignore unrecognized YAML tags instead of crashing

-  Explicitly disable XML entity expansion and mention in docs

-  xq -x: Raise understandable error on non-dict conversion failure

Changes for v2.4.0 (2018-02-08)
===============================

-  Support XML parsing with xmltodict

Changes for v2.3.7 (2018-02-07)
===============================

-  Fix for the –from-file/-f argument: Re-route jq_filter to files when
   using –from-file. Fixes #19.

Changes for v2.3.6 (2018-01-29)
===============================

-  Parse and pass multiple positional-consuming jq args

Changes for v2.3.5 (2018-01-29)
===============================

-  Support jq arguments that consume subsequent positionals (such as
   –arg k v) (#16).

Changes for v2.3.4 (2017-12-26)
===============================

-  Support bare YAML dates and times. Fixes #10

Changes for v2.3.3 (2017-09-30)
===============================

-  Avoid buffering all input docs in memory with no -y

-  End all json.dump output with newlines. Close all input streams.
   Fixes #8. Thanks to @bubbleattic for reporting.

Changes for v2.3.2 (2017-09-25)
===============================

-  Fix test suite on Python 3

Changes for v2.3.1 (2017-09-25)
===============================

-  Add support for multiple yaml files in arguments. Thanks to
   @bubbleattic (PR #7)

Changes for v2.3.0 (2017-08-27)
===============================

-  Handle multi-document streams. Fixes #6

-  Report version via yq --version

Changes for v2.2.0 (2017-07-07)
===============================

-  Stringify datetimes loaded from YAML. Fixes #5

Changes for v2.1.2 (2017-06-27)
===============================

-  Fix ResourceWarning: unclosed file

-  Internal: Make usage of loader argument consistent

-  Documentation improvements

Changes for v2.1.1 (2017-05-02)
===============================

-  Fix release script. Release is identical to v2.1.0.

Changes for v2.1.0 (2017-05-02)
===============================

-  yq now supports emitting YAML (round-trip YAML support) using "yq
   -y". Fixes #2.

-  Key order is now preserved in mappings/objects/dictionaries.

-  Passing input files by filename as an argument is now supported (in
   addition to providing data on standard input).

Changes for v2.0.2 (2017-01-16)
===============================

-  Test and documentation improvements

Changes for v2.0.1 (2017-01-14)
===============================

-  Fix description in setup.py

Changes for v2.0.0 (2017-01-14)
===============================

-  Begin 2.0.0 release series. This package's release series available
   on PyPI begins with version 2.0.0. Versions of ``yq`` prior to 2.0.0
   are distributed by https://github.com/abesto/yq and are not related
   to this package. No guarantees of compatibility are made between
   abesto/yq and kislyuk/yq. This package follows the
   ``Semantic   Versioning 2.0.0 <http://semver.org/>``\ \_ standard. To
   ensure proper operation, declare dependency version ranges according
   to SemVer. See the Readme for more information.
