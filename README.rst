yq: Command-line YAML/XML/TOML processor - jq wrapper for YAML, XML, TOML documents
===================================================================================

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

By default, no conversion of ``jq`` output is done. Use the ``--yaml-output``/``-y`` option to convert it back into YAML::

    cat input.yml | yq -y .foo.bar

Mapping key order is preserved. By default, custom `YAML tags <http://www.yaml.org/spec/1.2/spec.html#id2764295>`_ and
`styles <https://yaml.org/spec/current.html#id2509255>`_ in the input are ignored. Use the ``--yaml-roundtrip``/``-Y``
option to preserve YAML tags and styles by representing them as extra items in their enclosing mappings and sequences
while in JSON::

    yq -Y .foo.bar input.yml

Use the ``--width``/``-w`` option to pass the line wrap width for string literals. With ``-y/-Y``, files can be edited
in place like with ``sed -i``: ``yq -yi .foo=1 *.yml``. All other command line arguments are forwarded to ``jq``. ``yq``
forwards the exit code ``jq`` produced, unless there was an error in YAML parsing, in which case the exit code is 1.
See the `jq manual <https://stedolan.github.io/jq/manual/>`_ for more details on ``jq`` features and options.

Because YAML treats JSON as a dialect of YAML, you can use yq to convert JSON to YAML: ``yq -y . < in.json > out.yml``.

Preserving tags and styles using the ``-Y`` (``--yaml-roundtrip``) option
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``-Y`` option helps preserve custom `string styles <https://yaml-multiline.info/>`_ and
`tags <https://camel.readthedocs.io/en/latest/yamlref.html#tags>`_ in your document. For example, consider the following
document (an `AWS CloudFormation <https://aws.amazon.com/cloudformation/>`_ template fragment)::

    Resources:
      ElasticLoadBalancer:
        Type: 'AWS::ElasticLoadBalancing::LoadBalancer'
        Properties:
          AvailabilityZones: !GetAZs ''
          Instances:
            - !Ref Ec2Instance1
            - !Ref Ec2Instance2
          Description: >-
            Load balancer for Big Important Service.

            Good thing it's managed by this template.

Passing this document through ``yq -y .Resources.ElasticLoadBalancer`` will drop custom tags, such as ``!Ref``,
and styles, such as the `folded <https://yaml-multiline.info/>`_ style of the ``Description`` field::

    Type: AWS::ElasticLoadBalancing::LoadBalancer
    Properties:
      AvailabilityZones: ''
      Instances:
        - Ec2Instance1
        - Ec2Instance2
      Description: 'Load balancer for Big Important Service.

        Good thing it''s managed by this template.'

By contrast, passing it through ``yq -Y .Resources.ElasticLoadBalancer`` will preserve tags and styles::

    Type: 'AWS::ElasticLoadBalancing::LoadBalancer'
    Properties:
      AvailabilityZones: !GetAZs ''
      Instances:
        - !Ref 'Ec2Instance1'
        - !Ref 'Ec2Instance2'
      Description: >-
        Load balancer for Big Important Service.

        Good thing it's managed by this template.

To accomplish this in ``-Y`` mode, yq carries extra metadata (mapping pairs and sequence values) in the JSON
representation of your document for any custom tags or styles that it finds. When converting the JSON back into YAML, it
parses this metadata, re-applies the tags and styles, and discards the extra pairs and values.

.. warning ::

 The ``-Y`` option is incompatible with jq filters that do not expect the extra information injected into the document
 to preserve the YAML formatting. For example, a jq filter that counts entries in the Instances array will come up with
 4 entries instead of 2. A filter that expects all array entries to be mappings may break due to the presence of string
 metadata keys. Check your jq filter for compatibility/semantic validity when using the ``-Y`` option.

XML support
-----------
``yq`` also supports XML. The ``yq`` package installs an executable, ``xq``, which
`transcodes XML to JSON <https://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html>`_ using
`xmltodict <https://github.com/martinblech/xmltodict>`_ and pipes it to ``jq``. Roundtrip transcoding is available with
the ``xq --xml-output``/``xq -x`` option. Multiple XML documents can be passed in separate files/streams as
``xq a.xml b.xml``. Entity expansion and DTD resolution is disabled to avoid XML parsing vulnerabilities.

TOML support
------------
``yq`` supports `TOML <https://toml.io/>`_ as well. The ``yq`` package installs an executable, ``tomlq``, which uses the
`tomllib module <https://docs.python.org/3.11/library/tomllib.html>` or `tomli library
<https://github.com/hukkin/tomli>`_ to transcode TOML to JSON, then pipes it to ``jq``. Transcoding to TOML uses the
`tomli-w <https://github.com/hukkin/toml-w`_ package. Roundtrip transcoding
is available with the ``tomlq --toml-output``/``tomlq -t`` option.

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
* `Documentation <https://kislyuk.github.io/yq/>`_
* `Package distribution (PyPI) <https://pypi.python.org/pypi/yq>`_
* `Change log <https://github.com/kislyuk/yq/blob/master/Changes.rst>`_
* `jq <https://stedolan.github.io/jq/>`_ - the command-line JSON processor utility powering ``yq``

Bugs
~~~~
Please report bugs, issues, feature requests, etc. on `GitHub <https://github.com/kislyuk/yq/issues>`_.

License
-------
Licensed under the terms of the `Apache License, Version 2.0 <http://www.apache.org/licenses/LICENSE-2.0>`_.

.. image:: https://github.com/kislyuk/yq/workflows/Python%20package/badge.svg
        :target: https://github.com/kislyuk/yq/actions
.. image:: https://codecov.io/github/kislyuk/yq/coverage.svg?branch=master
        :target: https://codecov.io/github/kislyuk/yq?branch=master
.. image:: https://img.shields.io/pypi/v/yq.svg
        :target: https://pypi.python.org/pypi/yq
.. image:: https://img.shields.io/pypi/l/yq.svg
        :target: https://pypi.python.org/pypi/yq
