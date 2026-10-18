PYTHON ?= python3
CMAKE ?= cmake
BUILD ?= build
.PHONY: bootstrap build test differential integration evidence-test conversion-test demo benchmark verify sanitize mutation clean-verify fmt format lint typecheck security security-online real-model fetch-model release-verify
bootstrap:
	$(PYTHON) scripts/bootstrap.py
build:
	$(CMAKE) -S . -B $(BUILD) -G Ninja -DCMAKE_BUILD_TYPE=Release
	$(CMAKE) --build $(BUILD) -j 2
test: build
	ctest --test-dir $(BUILD) --output-on-failure
differential: build
	BQ_BINARY=$(BUILD)/batchquay $(PYTHON) -m unittest discover -s tests -p test_numerics.py -v
integration: build
	BQ_BINARY=$(BUILD)/batchquay $(PYTHON) -m unittest discover -s tests -p test_system.py -v
fetch-test:
	$(PYTHON) -m unittest discover -s tests -p test_fetch.py -v
evidence-test:
	$(PYTHON) -m unittest discover -s tests -p test_evidence.py -v
conversion-test: build
	BQ_BINARY=$(BUILD)/batchquay $(PYTHON) -m unittest discover -s tests -p test_conversion.py -v
demo: build
	BQ_BINARY=$(BUILD)/batchquay $(PYTHON) -m tools.demo
benchmark: build
	BQ_BINARY=$(BUILD)/batchquay $(PYTHON) -m tools.benchmark
fmt:
	$(PYTHON) scripts/style_check.py
format:
	clang-format -i src/*.cpp src/*.hpp tests/native_tests.cpp
lint: build
	$(PYTHON) scripts/analyze.py
typecheck: build
	$(PYTHON) -m compileall -q src tests tools scripts
security:
	$(PYTHON) scripts/check_integrity.py
	$(PYTHON) scripts/audit_public.py
security-online:
	$(PYTHON) scripts/security_online.py
verify: fmt test differential integration evidence-test fetch-test typecheck security demo
	@echo 'Core local verification passed. This is NOT full-product release approval.'
sanitize:
	$(CMAKE) -S . -B build-sanitize -G Ninja -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Debug -DBQ_SANITIZE=ON
	$(CMAKE) --build build-sanitize -j 2
	ctest --test-dir build-sanitize --output-on-failure
	BQ_BINARY=build-sanitize/batchquay $(PYTHON) -m unittest discover -s tests -p test_system.py -v
mutation: build
	$(PYTHON) scripts/negative_controls.py
clean-verify:
	$(PYTHON) scripts/clean_verify.py
fetch-model:
	$(PYTHON) -m tools.fetch_model
real-model: build
	$(PYTHON) -m tools.real_model
release-verify:
	$(PYTHON) -m scripts.release_verify
