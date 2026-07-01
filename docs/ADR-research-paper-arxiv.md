# ADR: arXiv research paper — a grounded LaTeX system description under docs/paper

Date: 2026-06-22
Status: Accepted (R0 — source landed, PDF built out-of-band)

## Context

kotoba already has three explanatory surfaces, each pitched at a different
reader:

- the **README** (operator / quickstart — install, run, endpoints),
- the **ADR set** (`docs/ADR-*.md` — per-decision rationale for contributors), and
- the **interactive HTML explainers** (`docs/explainer/` — narrated walkthroughs
  for a general audience).

What was missing is a single, self-contained, **citable** description of the
whole system: the data model, the storage and indexing layers, the query and
computation engines, the security architecture, and the runtime, written as one
linear argument with a bibliography. That is the artifact an outside researcher
links to, a reviewer reads end-to-end, and a future contributor uses as the
"why does this exist at all" map above the ADRs. The one-line definition
(`KOTOBA ≝ Datom[CID/T] × EAVT × Pregel[BSP] × Datalog[Δ] × CACAO × AT × LLM ×
WASM/WIT`) is the spine of such a paper but had never been written out as prose.

## Decision

Maintain an **arXiv-style preprint** as LaTeX source in the repository, under
`docs/paper/`, as a *derived, grounded* artifact — not a separate source of
truth.

```
docs/paper/
├── kotoba.tex      # article-class preprint; Abstract → References
├── references.bib  # BibTeX (Datomic, IPFS/IPLD, Prolly Tree, Pregel,
│                   #   differential dataflow, SPARQL, CACAO/CAIP-74, DID,
│                   #   AT Protocol, Signal X3DH/Double Ratchet, WASM
│                   #   Component Model, Shamir, Kotoba/EDN)
├── arxiv.yaml      # submission metadata (title, abstract, categories)
└── README.md       # build + submit instructions + claim→source map
```

### Format: LaTeX (arXiv standard), not Markdown

arXiv ingests LaTeX **source**, not a PDF, and runs `pdflatex`+`bibtex` on its
side. A Markdown paper would have to be converted and would lose the bibliography
and cross-reference machinery. So the canonical form is `kotoba.tex` +
`references.bib`; the PDF is a build output and is **not** checked in (no TeX
toolchain in the authoring environment — build locally or in CI via
`latexmk -pdf kotoba.tex`).

### Categories

Primary **cs.DB** (Databases); cross-list **cs.DC** (Distributed, Parallel, and
Cluster Computing) and **cs.CR** (Cryptography and Security). Recorded in
`arxiv.yaml` so the web-form / CI metadata has one source.

### Grounding contract (the load-bearing rule)

Every technical claim in the paper must be traceable to repository source or an
ADR. The paper is *downstream* of the code and the ADRs, the way the README is —
it never asserts behaviour the code does not have. `docs/paper/README.md` carries
the claim→source table (Prolly Tree → `kotoba-core/src/prolly.rs`, four-index →
`kotoba-query/src/arrangement.rs`, CACAO depth-2 → `kotoba-auth/src/cacao.rs`,
X3DH/Double Ratchet → `kotoba-signal/src/{x3dh,ratchet}.rs`, sealed tier →
`kotoba-store/src/sealed_store.rs`, five-axis roadmap →
`ADR-001-five-axis-distributed-redesign.md`, etc.). Benchmark numbers quoted in
the paper (e.g. 5,222 entities/s sustained ingest; 12,753 QPS CACAO-gated ASK at
c=32; ~180 ns EAVT point lookup) are the measured values already recorded in
`CLAUDE.md`'s benchmark section — not fresh, unaudited figures.

### Scope boundary

The paper describes the **read+verify / single-writer-per-graph** system as it
exists today and frames the multi-writer work (multi-parent DAG, HLC ordering,
CRDT merge, declared replication) as the roadmap of
`ADR-001-five-axis-distributed-redesign.md` rather than claiming it as shipped.
On-chain origination, settlement, and PDS publication remain
etzhayyim-exclusive (operating-entity boundary) and are out of scope for the
paper as for the rest of kotoba.

## Consequences

- One canonical, linkable description of the system exists; the "Availability"
  line points at the docs site (`com-junkawasaki.github.io/kotoba`).
- The paper inherits the same drift risk as the explainers: when a subsystem
  changes materially, `kotoba.tex` and the claim→source table must be updated in
  the same spirit as the README. The grounding contract makes such drift a
  reviewable diff rather than silent rot.
- No build-system change: the repo does not gain a TeX dependency; PDF
  construction is an optional CI job (`xu-cheng/latex-action`), not part of
  `cargo` or Pages.
- The `arxiv.yaml` metadata is advisory (not consumed by LaTeX); if it diverges
  from `kotoba.tex`'s title/abstract, the `.tex` wins.

## R0 honesty / follow-ups

- **PDF not in-repo / not CI-built yet.** Source compiles by construction
  (env/label/cite balance machine-checked: 0 undefined refs, 0 missing cites,
  braces balanced) but has not been run through a real `pdflatex` in this
  environment. Adding the `latex-action` CI step that builds `kotoba.pdf` on
  changes to `docs/paper/**` is the next increment.
- **Not yet submitted to arXiv.** `arxiv.yaml` is prepared; actual submission
  (endorsement, license selection) is a manual, author-initiated step.
- **Figures are tables-only.** The paper currently uses prose + tables; the SVG
  architecture diagrams under `docs/` are not yet imported as TikZ/`\includegraphics`.
- **Drift guard is manual.** There is no automated check that paper claims still
  match source (unlike `kotoba word diff`). A lightweight linter that greps the
  claim→source table paths for existence would catch the cheapest class of rot.
