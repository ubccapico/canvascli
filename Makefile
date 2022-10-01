.PHONY: all

all: build upload clean

build:
	python -m build

upload:
	python -m twine upload dist/*

clean:
	rm -rf dist/*
