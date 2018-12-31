PYTHON ?= python

all: build

.PHONY:

build:
	$(PYTHON) setup.py build_ext -i
	cargo build

clean:
	$(PYTHON) setup.py clean --all
	rm -f sourmash/*.so
	cd doc && make clean

install: all
	$(PYTHON) setup.py install

dist: FORCE
	$(PYTHON) setup.py sdist

test: all
	cargo test
	pip install -e '.[test]'
	$(PYTHON) -m pytest

doc: .PHONY
	cd doc && make html

include/sourmash.h: src/lib.rs src/ffi/minhash.rs src/ffi/signature.rs src/errors.rs
	rustup override set nightly
	RUST_BACKTRACE=1 cbindgen --clean -c cbindgen.toml -o $@
	rustup override set stable

coverage: all
	$(PYTHON) setup.py clean --all
	SOURMASH_COVERAGE=1 $(PYTHON) setup.py build_ext -i
	$(PYTHON) -m pytest --cov=. --cov-report term-missing

benchmark:
	asv continuous master $(git rev-parse HEAD)
	cargo bench

check:
	cargo build
	cargo test
	cargo bench

last-tag:
	git fetch -p -q; git tag -l | sort -V | tail -1

wasm:
	wasm-pack build

FORCE:
