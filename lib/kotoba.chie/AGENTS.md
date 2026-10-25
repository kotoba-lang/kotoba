# chie 智慧 — AI-ecosystem Knowledge Graph mirror

**ADR**: 2606171200 · **depends**: 2606011800 (tsumugi 産霊の網 / engi-organism) · 2605081300
(edge-primary karma) · 2605312345 (Datom = canonical state) · 2605262130 (kotoba) · 2605215000
(Murakumo-only) · 2606091000 (commit-DAG heartbeat) · 2605192415 (cell-runner). **Status**:
🟢 R1+ (clj-native, kotoba/Datom-native, 常駐化 heartbeat + Murakumo digest + DISCLOSED ingest
with G7 gate, on the **root kotoba roster** — 105 entities / 0 drift / 0 violations,
66-node seed all kinds/edges/axes covered, KG query API, rounds+policy authoritative ingest,
integrity/charter self-audit, Datalog read path over the kotoba engine, 56 tests / 184 assertions green).

chie ("智慧" = wisdom/intelligence) is the **AI sibling** of the power-mirror lineage
(tsumugi / keizu / kabuto / kanjō / kosatsu). It applies the same KG-mirror architecture to
the **AI ecosystem**: it weaves **labs / companies / research bodies / standards bodies /
funders / states / public-role persons / policy instruments / models** and the **縁** between
them (invests-in / compute-deal / talent-flow / governs / sets-standard / partners /
holds-role / depends-on) into the kotoba Datom log, and runs an **edge-primary
取-concentration** pass over **four axes — compute / capital / talent / policy** — **routed to
OPENING** (open-weights / open-compute / anti-monopoly).

It closes a roster coverage gap: the AI ecosystem as a unified, EDN/Clojure-native graph
(有力者・企業・組織・投資・政策) previously had **no single actor** — only scattered
fragments (tsumugi power, kabuto supply, kanjō financials, handotai/kasa hardware,
kenkyusha research frontiers, and `*-compat` API facades).

## Hard gates (constitutional — read before any change)

- **G1 — OPENING map, NEVER a target-list or winner-ranking.** This is the defining
  inversion. `:bond/opening-priority` = Σ inbound accumulation × **(1 − openness)** — an
  **open** accumulator scores **0** even when it accumulates heavily. chie does NOT grade
  capability, forecast winners, or rank "who will win". The 取-holder is the accumulator; the
  routing is **opening** (release of the concentration). _(test-enforced:
  `test-g1-open-accumulator-scores-zero`)_
- **G2 — edge-primary (N1).** 取 lives ONLY on edges (`:en/grasping-load`). A node's
  priority = the **integral of its incident inbound accumulation edges**, computed **on
  read** — never a stored per-entity score. There is no `:ai/score-of-lab`. Persons appear
  ONLY as **public-power role nodes** (`:ai.role/person`), never private profiles.
- **G3 — non-adjudicating (N3).** Funding rounds, regulator designations, and `:ai/open?`
  flags are **DISCLOSED facts**, never chie verdicts. `:ai/open?` flags the *weights*, not
  capability worth.
- **G4 — chie never trades / never forecasts.** `:trade` / `:forecast-point` /
  `:capability-grade` / `:winner-rank` are **unrepresentable** (no such edge / attr). The
  Datom emitter refuses to emit them. _(test-enforced: `test-no-trade-no-score-attrs`)_
- **G5 — sourcing honesty.** Every record carries `:organism/sourcing :authoritative |
  :representative`. The committed seed is **all `:representative`** and coverage is ~0 by
  design; `coverage_report` names the gaps (no fabricated coverage).
- **G6 — Murakumo-only narration.** Any future LLM narration routes through Murakumo
  (ADR-2605215000).
- **G7 — outward-gated.** Live planet-scale ingest (regulator texts / disclosed rounds /
  Wikidata) requires Council + operator DID. R0 = analyzer + schema + seed only.

## Layout

```
./
├── AGENTS.md                              # this file
├── wire/manifest.jsonld                        # actor manifest
├── MATURITY.md                            # maturity scorecard + roadmap
├── kotoba/
│   └── schema.edn                         # AI-ecosystem ontology (nodes / 縁 / axes / forbidden)
├── data/
│   └── seed.edn       # real PUBLIC AI-ecosystem graph (representative)
├── src/chie/methods/                               # clj-native (.cljc), kotoba pywasm-target IS the source
│   ├── analyze.cljc                       # edge-primary 取-concentration → OPENING
│   ├── datom_emit.cljc                    # kotoba Datom-log (EAVT) emitter — canonical state
│   ├── coverage_report.cljc               # honest coverage + gap map (G5)
│   └── test_datom_emit.cljc
├── test/
│   ├── test_analyze.cljc
│   └── test_coverage.cljc
└── out/                                    # GENERATED — do not hand-edit / not committed
```

## Run

```bash
# from repo root (bb.edn classpath roots 20-actors)
kbb -M:test:actors           # auto-discovers chie.tests.* + chie.methods.test-* (18 assertions-suite)
```

The three test namespaces are picked up automatically by `etzhayyim.tools.discovery`
(ADR-2606131500) — no bb.edn churn.

## Ontology (`data/schema/ontology.edn`)

- **nodes** `:organism/kind` ∈ the 11 `:ai.*` kinds; facets `:ai/sector`, `:ai/open?`.
- **edges** `:en/kind` ∈ `{:invests-in :compute-deal :talent-flow :governs :sets-standard
  :partners :holds-role :depends-on}` carrying `:en/grasping-load` ∈ [0,1] (where 取 lives).
- **axes** compute / capital / talent / policy → routed to **OPENING**.
- **derived** `:bond/opening-priority` · `:bond/reach-imposed` · `:bond/dependency-fragility`
  — transient, computed on read, never persisted (N1/G2).

## Cross-links

chie **references**, never duplicates: financials → **kanjō**, supply-chain → **kabuto**,
silicon → **handotai**, compute capacity → **kasa**, research frontiers → **kenkyusha**,
government power → **keizu**, designations → **kosatsu**, antitrust routing → **abaki**.
chie observes the AI field; it does not adjudicate, target, grade, or trade.
