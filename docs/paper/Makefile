PAPER = kotoba
SOURCES = $(PAPER).tex references.bib
BUILD_EXT = aux bbl blg fdb_latexmk fls log out pdf

.PHONY: all clean dist arxiv check

all: $(PAPER).pdf

$(PAPER).pdf: $(SOURCES)
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex; \
	elif command -v tectonic >/dev/null 2>&1; then \
		tectonic $(PAPER).tex; \
	else \
		echo "Need latexmk or tectonic to build $(PAPER).pdf" >&2; \
		exit 1; \
	fi

dist: arxiv

arxiv: $(SOURCES)
	mkdir -p build/arxiv
	cp $(SOURCES) build/arxiv/
	cd build/arxiv && tar -czf ../$(PAPER)-arxiv-source.tar.gz $(SOURCES)
	@echo "Created docs/paper/build/$(PAPER)-arxiv-source.tar.gz"

check: $(PAPER).pdf arxiv

clean:
	@if command -v latexmk >/dev/null 2>&1; then latexmk -C $(PAPER).tex; fi
	rm -rf build
	for ext in $(BUILD_EXT); do rm -f "$(PAPER).$$ext"; done
