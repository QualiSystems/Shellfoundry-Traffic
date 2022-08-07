
repo=localhost
user=pypiadmin
password=pypiadmin

.PHONY: build

clean:
	rm -rf dist/*
	rm -rf *.egg-info
	rm -rf build

install:
	make clean
	python -m pip install -U pip
	pip install -U -r requirements-dev.txt

build:
	make clean
	python setup.py bdist_wheel

upload:
	make build
	twine upload --repository-url http://$(repo):8036 --user $(user) --password $(password) dist/*
