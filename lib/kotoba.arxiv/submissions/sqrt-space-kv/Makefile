PAPER = sqrt_space_kv
SOURCE_DIR = source
SOURCES = $(SOURCE_DIR)/$(PAPER).tex $(SOURCE_DIR)/references.bib
BUILD_DIR = build

.PHONY: all clean arxiv check

all: $(PAPER).pdf

$(PAPER).pdf: $(SOURCES)
	@if command -v tectonic >/dev/null 2>&1; then \
		(cd $(SOURCE_DIR) && tectonic $(PAPER).tex); \
		cp $(SOURCE_DIR)/$(PAPER).pdf $(PAPER).pdf; \
	elif command -v latexmk >/dev/null 2>&1; then \
		(cd $(SOURCE_DIR) && latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex); \
		cp $(SOURCE_DIR)/$(PAPER).pdf $(PAPER).pdf; \
	else \
		echo "Need tectonic or latexmk" >&2; exit 1; \
	fi

arxiv: $(SOURCES)
	mkdir -p $(BUILD_DIR)/arxiv
	cp $(SOURCES) $(BUILD_DIR)/arxiv/
	# arXiv wants .bbl or bibtex-processable; ship .bib + note to run bibtex
	cd $(BUILD_DIR)/arxiv && tar -czf ../$(PAPER)-arxiv-source.tar.gz $(PAPER).tex references.bib
	@echo "Created build/$(PAPER)-arxiv-source.tar.gz"

check: $(PAPER).pdf arxiv

clean:
	rm -rf $(BUILD_DIR) $(PAPER).pdf $(SOURCE_DIR)/$(PAPER).pdf \
	  $(SOURCE_DIR)/$(PAPER).aux $(SOURCE_DIR)/$(PAPER).log \
	  $(SOURCE_DIR)/$(PAPER).out $(SOURCE_DIR)/$(PAPER).bbl \
	  $(SOURCE_DIR)/$(PAPER).blg
