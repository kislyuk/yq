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
