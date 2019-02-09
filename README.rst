yq: Command-line YAML/XML processor - jq wrapper for YAML and XML documents
===========================================================================

Installation
------------
::

    pip install yq

Before using ``yq``, you also have to install its dependency, ``jq``. See the `jq installation instructions
<https://stedolan.github.io/jq/download/>`_ for details and directions specific to your platform.

On macOS, ``yq`` is also available on `Homebrew <https://brew.sh/>`_: use ``brew install python-yq``.

Synopsis
--------

``yq`` takes YAML input, converts it to JSON, and pipes it to `jq <https://stedolan.github.io/jq/>`_::

    cat input.yml | yq .foo.bar

Like in ``jq``, you can also specify input filename(s) as arguments::

    yq .foo.bar input.yml

By default, no conversion of ``jq`` output is done. Use the ``--yaml-output``/``-y`` argument to convert it back into YAML::

    cat input.yml | yq -y .foo.bar

Use the ``--width``/``-w`` argument to pass the line wrap width for string literals. All other command line arguments are
forwarded to ``jq``. ``yq`` forwards the exit code ``jq`` produced, unless there was an error in YAML parsing, in which case
the exit code is 1. See the `jq manual <https://stedolan.github.io/jq/manual/>`_ for more details on ``jq`` features and
options.

YAML `tags <http://www.yaml.org/spec/1.2/spec.html#id2764295>`_ in the input are ignored (any nested data is treated as
untagged). Key order is preserved.

Because YAML treats JSON as a dialect of YAML, you can use yq to convert JSON to YAML: ``yq -y . < in.json > out.yml``.

XML support
-----------
``yq`` also supports XML. The ``yq`` package installs an executable, ``xq``, which
`transcodes XML to JSON <https://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html>`_ using
`xmltodict <https://github.com/martinblech/xmltodict>`_ and pipes it to ``jq``. Roundtrip transcoding is available with
the ``xq --xml-output``/``xq -x`` option. Multiple XML documents can be passed in separate files/streams as
``xq a.xml b.xml``. Entity expansion and DTD resolution is disabled to avoid XML parsing vulnerabilities.

.. admonition:: Compatibility note

 This package's release series available on PyPI begins with version 2.0.0. Versions of ``yq`` prior to 2.0.0 are
 distributed by https://github.com/abesto/yq and are not related to this package. No guarantees of compatibility are
 made between abesto/yq and kislyuk/yq. This package follows the `Semantic Versioning 2.0.0 <http://semver.org/>`_
 standard. To ensure proper operation, declare dependency version ranges according to SemVer.

Authors
-------
* Andrey Kislyuk

Links
-----
* `Project home page (GitHub) <https://github.com/kislyuk/yq>`_
* `Documentation (Read the Docs) <https://yq.readthedocs.io/en/latest/>`_
* `Package distribution (PyPI) <https://pypi.python.org/pypi/yq>`_
* `Change log <https://github.com/kislyuk/yq/blob/master/Changes.rst>`_
* `jq <https://stedolan.github.io/jq/>`_ - the command-line JSON processor utility powering ``yq``

Bugs
~~~~
Please report bugs, issues, feature requests, etc. on `GitHub <https://github.com/kislyuk/yq/issues>`_.

License
-------
Licensed under the terms of the `Apache License, Version 2.0 <http://www.apache.org/licenses/LICENSE-2.0>`_.

.. image:: https://img.shields.io/travis/kislyuk/yq.svg
        :target: https://travis-ci.org/kislyuk/yq
.. image:: https://codecov.io/github/kislyuk/yq/coverage.svg?branch=master
        :target: https://codecov.io/github/kislyuk/yq?branch=master
.. image:: https://img.shields.io/pypi/v/yq.svg
        :target: https://pypi.python.org/pypi/yq
.. image:: https://img.shields.io/pypi/l/yq.svg
        :target: https://pypi.python.org/pypi/yq
.. image:: https://readthedocs.org/projects/yq/badge/?version=latest
        :target: https://yq.readthedocs.io/
