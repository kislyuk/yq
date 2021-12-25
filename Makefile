test_deps:
	pip install .[tests]

lint: test_deps
	flake8 $$(python setup.py --name)

test: test_deps lint
	coverage run --source=$$(python setup.py --name) ./test/test.py -v

docs:
	sphinx-build docs docs/html

install: clean
	pip install build
	python -m build
	pip install --upgrade dist/*.whl

clean:
	-rm -rf build dist
	-rm -rf *.egg-info

.PHONY: lint test test_deps docs install clean

include common.mk
