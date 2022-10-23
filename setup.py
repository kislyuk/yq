#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="yq",
    version="3.1.0",
    url="https://github.com/kislyuk/yq",
    license="Apache Software License",
    author="Andrey Kislyuk",
    author_email="kislyuk@gmail.com",
    description="Command-line YAML/XML processor - jq wrapper for YAML/XML documents",
    long_description=open("README.rst").read(),
    python_requires=">=3.6",
    use_scm_version={
        "write_to": "yq/version.py",
    },
    setup_requires=['setuptools_scm >= 3.4.3'],
    install_requires=[
        "PyYAML >= 5.3.1",
        "xmltodict >= 0.11.0",
        "tomli >= 1.2.3; python_version < '3.11'",
        "tomli-w",
        "argcomplete >= 1.8.1"
    ],
    extras_require={
        "tests": [
            "coverage",
            "flake8",
            "wheel"
        ]
    },
    packages=find_packages(exclude=["test"]),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'yq=yq:cli',
            'xq=yq:xq_cli',
            'tomlq=yq:tq_cli'
        ],
    },
    test_suite="test",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ]
)
