test_deps:
	pip install .[tests]

version: yq/version.py
yq/version.py: setup.py
	echo "__version__ = '$$(python setup.py --version)'" > $@

lint: test_deps
	flake8 $$(python setup.py --name)

test: test_deps lint
	coverage run --source=$$(python setup.py --name) ./test/test.py -v

docs:
	sphinx-build docs docs/html

install: clean version
	pip install build
	python -m build
	pip install --upgrade dist/*.whl

clean:
	-rm -rf build dist
	-rm -rf *.egg-info

.PHONY: lint test test_deps docs install clean

include common.mk
