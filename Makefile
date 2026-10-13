# `make check` compiles every example under PDF/UA-1 (what the CI runs).
EXAMPLES := $(wildcard examples/*.typ)
PDFS := $(EXAMPLES:examples/%.typ=build/%.pdf)

check: $(PDFS)
	@echo "all examples compiled"

build/%.pdf: examples/%.typ $(wildcard themes/*.typ) $(wildcard notes/*.typ)
	@mkdir -p build
	typst compile --root . --pdf-standard ua-1 $< $@

# `make logbook`: the log-book format's tests and the example book through the checker (needs uv).
logbook:
	uv run --project logbook --extra test pytest -q logbook/tests
	uv run --project logbook logbook --root examples/logbook check

clean:
	rm -rf build

.PHONY: check clean logbook
