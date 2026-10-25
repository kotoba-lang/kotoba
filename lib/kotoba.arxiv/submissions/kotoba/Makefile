PAPER = kotoba
SOURCE_DIR = source
SOURCES = $(SOURCE_DIR)/$(PAPER).tex $(SOURCE_DIR)/references.bib
BUILD_DIR = build

.PHONY: all clean arxiv check

all: $(PAPER).pdf

$(PAPER).pdf: $(SOURCES)
	@if command -v latexmk >/dev/null 2>&1; then \
		(cd $(SOURCE_DIR) && latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex); \
		cp $(SOURCE_DIR)/$(PAPER).pdf $(PAPER).pdf; \
	elif command -v tectonic >/dev/null 2>&1; then \
		(cd $(SOURCE_DIR) && tectonic $(PAPER).tex); \
		cp $(SOURCE_DIR)/$(PAPER).pdf $(PAPER).pdf; \
	else \
		echo "Need latexmk or tectonic to build $(PAPER).pdf" >&2; \
		exit 1; \
	fi

arxiv: $(SOURCES)
	mkdir -p $(BUILD_DIR)/arxiv
	cp $(SOURCES) $(BUILD_DIR)/arxiv/
	cd $(BUILD_DIR)/arxiv && tar -czf ../$(PAPER)-arxiv-source.tar.gz $(PAPER).tex references.bib
	@echo "Created submissions/kotoba/$(BUILD_DIR)/$(PAPER)-arxiv-source.tar.gz"

check: $(PAPER).pdf arxiv

clean:
	@if command -v latexmk >/dev/null 2>&1; then cd $(SOURCE_DIR) && latexmk -C $(PAPER).tex; fi
	rm -rf $(BUILD_DIR) $(PAPER).pdf
	rm -f $(SOURCE_DIR)/$(PAPER).pdf
