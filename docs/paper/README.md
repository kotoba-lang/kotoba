# Kotoba — research paper (arXiv preprint)

This directory holds the LaTeX source for the \kotoba research paper, laid out
as a self-contained arXiv submission.

```
docs/paper/
├── kotoba.tex      # main paper (article class, arXiv-ready)
├── references.bib  # bibliography (BibTeX)
├── arxiv.yaml      # arXiv submission metadata (title, abstract, categories)
└── README.md       # this file
```

## Build

Requires a TeX distribution (TeX Live / MacTeX) with `pdflatex` and `bibtex`.

```bash
cd docs/paper
latexmk -pdf kotoba.tex          # preferred (runs bibtex automatically)
```

Or manually:

```bash
pdflatex kotoba
bibtex   kotoba
pdflatex kotoba
pdflatex kotoba
```

The output is `kotoba.pdf`.

> **Note:** no TeX toolchain is installed in the authoring environment, so the
> PDF is not checked in. Build it locally or in CI. A minimal CI step:
>
> ```yaml
> - uses: xu-cheng/latex-action@v3
>   with:
>     root_file: docs/paper/kotoba.tex
> ```

## Submitting to arXiv

arXiv accepts the LaTeX **source**, not a PDF. Upload `kotoba.tex` and
`references.bib` together (arXiv runs `pdflatex`+`bibtex` on its side). Suggested
primary category **cs.DB** (Databases) with cross-lists **cs.DC** (Distributed,
Parallel, and Cluster Computing) and **cs.CR** (Cryptography and Security). See
`arxiv.yaml` for the prepared title, abstract, and category list.

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
| Clojure → WASM            | `crates/kotoba-clj/` |
| Five-axis roadmap         | `docs/ADR-001-five-axis-distributed-redesign.md` |
| Sealed cold tier          | `docs/ADR-sealed-cold-tier.md` |
| Clojure-WASM ADR          | `docs/ADR-clojure-wasm.md` |
