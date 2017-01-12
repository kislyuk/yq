#!/usr/bin/env python

import os, glob
from setuptools import setup, find_packages

setup(
    name="ddbcli",
    version="0.0.1",
    url="https://github.com/kislyuk/ddbcli",
    license="Apache Software License",
    author="Andrey Kislyuk",
    author_email="kislyuk@gmail.com",
    description="A DynamoDB Command Line Interface with JSON I/O",
    long_description=open("README.rst").read(),
    install_requires=[
        "setuptools",
        "boto3 >= 1.4.2, < 2",
        "awscli"
    ],
    packages=find_packages(exclude=["test"]),
    include_package_data=True,
    platforms=["MacOS X", "Posix"],
    test_suite="test",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ]
)
