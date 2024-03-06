
SRC = tlstester.py

.PHONY: default pycodestyle mypy

default: pycodestyle mypy

pycodestyle: venv/bin/pycodestyle
	$^ $(SRC)

mypy: venv/bin/mypy
	$^ $(SRC)

venv/bin/pycodestyle: venv/bin/pip
	./venv/bin/pip install pycodestyle

venv/bin/mypy: venv/bin/pip
	./venv/bin/pip install mypy

venv/bin/pip:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

