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
