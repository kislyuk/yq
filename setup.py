#!/usr/bin/env python

from setuptools import setup, find_packages

tests_require = ["coverage", "flake8", "wheel"]

setup(
    name="yq",
    version="2.8.1",
    url="https://github.com/kislyuk/yq",
    license="Apache Software License",
    author="Andrey Kislyuk",
    author_email="kislyuk@gmail.com",
    description="Command-line YAML/XML processor - jq wrapper for YAML/XML documents",
    long_description=open("README.rst").read(),
    install_requires=[
        "setuptools",
        "PyYAML >= 3.11",
        "xmltodict >= 0.11.0"
    ],
    tests_require=tests_require,
    extras_require={
        "test": tests_require,
        "toml": ["toml >= 0.9.4"]
    },
    packages=find_packages(exclude=["test"]),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'yq=yq:cli',
            'xq=yq:xq_cli'
        ],
    },
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
