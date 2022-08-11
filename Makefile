.PHONY: build

repo=localhost
user=pypiadmin
password=pypiadmin

clean:
	rm -rf dist/*
	rm -rf *.egg-info
	rm -rf build

install:
	make clean
	python -m pip install -U pip
	pip install -U -r requirements.txt

build:
	make clean
	python -m build . --wheel

test:
	cd tests; pytest test_test_helpers.py
	cd tests/shell;	pytest test_shellfoundry_traffic_shell.py
	cd tests/script; pytest test_shellfoundry_traffic_script.py

upload:
	make build
	twine upload --repository-url http://$(repo):8036 --user $(user) --password $(password) dist/*
