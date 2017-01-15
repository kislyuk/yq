yq: Command-line YAML processor - jq wrapper for YAML documents
===============================================================

Installation
------------
::

    pip install yq

Before using ``yq``, you also have to install its dependency, ``jq``. See the `jq installation instructions
<https://stedolan.github.io/jq/download/>`_ for details and directions specific to your platform.

Synopsis
--------

yq's mode of operation is very basic: it transcodes YAML on standard input to JSON and pipes it to ``jq``, while passing
all of its command line options to jq.

.. code-block:: bash

    cat input.yml | yq .foo.bar

See the `jq manual <https://stedolan.github.io/jq/manual/>`_ for more details on jq features and options.

Authors
-------
* Andrey Kislyuk

Links
-----
* `Project home page (GitHub) <https://github.com/kislyuk/yq>`_
* `Documentation (Read the Docs) <https://yq.readthedocs.io/en/latest/>`_
* `Package distribution (PyPI) <https://pypi.python.org/pypi/yq>`_
* `Change log <https://github.com/kislyuk/yq/blob/master/Changes.rst>`_

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
