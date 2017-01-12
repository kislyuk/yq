DynamoQ: A DynamoDB command line interface with JSON I/O
========================================================

Installation
------------
::

    pip install dynamoq

Synopsis
--------

Use ``aws configure`` to set up your AWS command line environment.

.. code-block:: bash

    dynamoq get TABLE_NAME HASH_KEY
    DYNAMODB_TABLE=mytable dynamoq get HASH_KEY

    dynamoq put mytable '{"key": "foo", "data": "xyz"}' '{"key": "bar", "data": "xyz"}'
    dynamoq scan mytable

    echo '{"data": "update"}' | dynamoq update mytable mykey
    dynamoq update mytable mykey field1=2 field2=[] --condition "field3 eq 456"
    dynamoq update mytable mykey field1=2 field2=[] --condition "field4 between 7,8"

See `DynamoDB Conditions
<http://boto3.readthedocs.io/en/latest/reference/customizations/dynamodb.html#ref-dynamodb-conditions>`_ for more.

Authors
-------
* Andrey Kislyuk

Links
-----
* `Project home page (GitHub) <https://github.com/kislyuk/dynamoq>`_
* `Documentation (Read the Docs) <https://dynamoq.readthedocs.io/en/latest/>`_
* `Package distribution (PyPI) <https://pypi.python.org/pypi/dynamoq>`_
* `Change log <https://github.com/kislyuk/dynamoq/blob/master/Changes.rst>`_

Bugs
~~~~
Please report bugs, issues, feature requests, etc. on `GitHub <https://github.com/kislyuk/dynamoq/issues>`_.

License
-------
Licensed under the terms of the `Apache License, Version 2.0 <http://www.apache.org/licenses/LICENSE-2.0>`_.

.. image:: https://img.shields.io/travis/kislyuk/dynamoq.svg
        :target: https://travis-ci.org/kislyuk/dynamoq
.. image:: https://codecov.io/github/kislyuk/dynamoq/coverage.svg?branch=master
        :target: https://codecov.io/github/kislyuk/dynamoq?branch=master
.. image:: https://img.shields.io/pypi/v/dynamoq.svg
        :target: https://pypi.python.org/pypi/dynamoq
.. image:: https://img.shields.io/pypi/l/dynamoq.svg
        :target: https://pypi.python.org/pypi/dynamoq
.. image:: https://readthedocs.org/projects/dynamoq/badge/?version=latest
        :target: https://dynamoq.readthedocs.io/
