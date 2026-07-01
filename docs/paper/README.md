# Kotoba — research paper (arXiv preprint)

This directory holds the LaTeX source for the \kotoba research paper, laid out
as a self-contained arXiv submission.

```
docs/paper/
├── kotoba.tex      # main paper (article class, arXiv-ready)
├── references.bib  # bibliography (BibTeX)
├── arxiv.yaml      # arXiv submission metadata (title, abstract, categories)
├── Makefile        # PDF/source archive helpers
└── README.md       # this file
```

## Build

Requires either `latexmk` from TeX Live / MacTeX or `tectonic`.

```bash
cd docs/paper
make check                       # builds PDF and arXiv source archive
```

Or manually:

```bash
pdflatex kotoba
bibtex   kotoba
pdflatex kotoba
pdflatex kotoba
```

The output is `kotoba.pdf`.
The arXiv source archive is `build/kotoba-arxiv-source.tar.gz`.

> **Note:** this environment has `tectonic`, so the PDF build is verified. A
> minimal CI step using TeX Live:
>
> ```yaml
> - uses: xu-cheng/latex-action@v3
>   with:
>     root_file: docs/paper/kotoba.tex
> ```

## Submitting to arXiv

arXiv accepts the LaTeX **source**, not a PDF. Upload `kotoba.tex` and
`references.bib` together, or upload `build/kotoba-arxiv-source.tar.gz` after
running `make arxiv`. Suggested primary category **cs.DB** (Databases) with
cross-lists **cs.DC** (Distributed, Parallel, and Cluster Computing) and
**cs.CR** (Cryptography and Security). See `arxiv.yaml` for the prepared title,
abstract, and category list.

Recommended arXiv web-form values:

| Field | Value |
|---|---|
| Title | `Kotoba: A Content-Addressed Datalog Substrate for Accountable Decentralized Agent Memory` |
| Primary category | `cs.DB` |
| Cross-lists | `cs.DC`, `cs.CR` |
| Comments | `System description. Source and interactive explainers at https://com-junkawasaki.github.io/kotoba/` |
| License | `CC BY 4.0` if you want maximum reuse, otherwise arXiv's non-exclusive license |

## Grounding

Every technical claim in the paper is grounded in the repository source and the
design records under [`docs/`](../). Key references:

| Paper section | Source |
|---|---|
| Prolly Tree / CID         | `crates/kotoba-core/src/{prolly,cid,frame}.rs` |
| Datom write/query path    | `crates/kotoba-graph/src/{quad_store,commit,sparql}.rs` |
| Four-index arrangement    | `crates/kotoba-query/src/arrangement.rs` |
| Incremental Datalog / MV  | `crates/kotoba-query/src/{datalog,mv}.rs` |
| Pregel BSP                | `crates/kotoba-vm/src/pregel.rs` |
| CACAO delegation          | `crates/kotoba-auth/src/cacao.rs` |
| Signal X3DH / Double Ratchet | `crates/kotoba-signal/src/{x3dh,ratchet}.rs` |
| Tiered / sealed store     | `crates/kotoba-store/src/{tiered_store,sealed_store}.rs` |
| WASM host / WIT           | `crates/kotoba-runtime/src/executor.rs`, `wit/world.wit` |
| `kotoba wasm` / Kotoba/EDN → WASM | `crates/kotoba-cli/`, `crates/kotoba-clj/` |
| Five-axis roadmap         | `docs/ADR-001-five-axis-distributed-redesign.md` |
| Sealed cold tier          | `docs/ADR-sealed-cold-tier.md` |
| Kotoba-WASM ADR           | `docs/ADR-kotoba-wasm.md` |
