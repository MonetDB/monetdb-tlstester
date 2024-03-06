
SRC = tlstester.py

.PHONY: default pycodestyle

default: pycodestyle

pycodestyle: venv/bin/pycodestyle
	$^ $(SRC)

venv/bin/pycodestyle: venv/bin/pip
	./venv/bin/pip install pycodestyle

venv/bin/pip:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

