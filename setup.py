#!/usr/bin/env python

import os, glob
from setuptools import setup, find_packages

setup(
    name="yq",
    version="2.0.0",
    url="https://github.com/kislyuk/yq",
    license="Apache Software License",
    author="Andrey Kislyuk",
    author_email="kislyuk@gmail.com",
    description="FIXME",
    long_description=open("README.rst").read(),
    install_requires=[
        "setuptools",
        "PyYAML >= 3.11"
    ],
    packages=find_packages(exclude=["test"]),
    scripts=glob.glob("scripts/*"),
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
