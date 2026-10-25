# chie 智慧 — maturity scorecard

**ADR-2606171200** · status **🟢 R1** (clj-native · kotoba/Datom-native · 常駐化 heartbeat · tests green).

## Scorecard

| Dimension | State | Evidence |
|---|---|---|
| Ontology | ✅ | `data/schema/ontology.edn` — 11 node kinds · 8 edge kinds · 4 axes · forbidden set |
| Seed (representative) | ✅ | `data/seed.edn` — 66 nodes / 58 縁; **all 11 kinds + 8 edge kinds + 4 axes covered** (incl. invest/round + asset/compute) |
| Analyzer (edge-primary) | ✅ | `src/chie/methods/analyze.cljk` — opening / reach / fragility + 4-axis concentration, on-read |
| Datom emitter (EAVT) | ✅ | `src/chie/methods/datom_emit.cljk` — GROUND `:add` + DERIVED `:derived` (transient), deterministic |
| Coverage / gap honesty | ✅ | `src/chie/methods/coverage_report.cljk` — sourcing split + gap worklist, "~0 by design" |
| Murakumo digest | ✅ | `src/chie/methods/digest.cljk` — deterministic `template-digest` + Murakumo-only `narrate` (fail-open, non-fleet endpoint refused); wired into the heartbeat summary (narration, not persisted) |
| DISCLOSED ingest + G7 gate | ✅ | `src/chie/methods/ingest.cljk` — offline `ingest-file`/`ingest-files` upgrade **rounds + policy instruments** → `:authoritative` (round amount + official-source `:en/disclosed-src` on rounds/governs edges; idempotent, concentration-preserving). 2 fixtures (rounds + EU-AI-Act/US-EO/広島/CoE w/ real URLs) → **8 :authoritative nodes**; `ingest-live` REFUSES without `CHIE_INGEST_LIVE` + operator DID (G7, tested) |
| **root kotoba roster** | ✅ | `00-contracts/schemas/ai-ecosystem-ontology.kotoba.edn` (db/ident vocab) + seed names its `vocabulary:` → `kbb -M:kotoba:ingest --validate` = **105 entities / 589 datoms / 0 undeclared / 0 value-violations**; `kbb -M:kotoba:roster-report` lists chie (27/27 actors clean). Drift-guard test locks seed↔schema |
| Datalog read path (datomic) | ✅ | `src/chie/methods/kqe.cljk` — ingests the seed into the REAL `etzhayyim.kotoba.engine` + queries via Datalog `q` + Datomic `pull` (VAET reverse-ref); engine result == in-memory `query.cljc` (test-enforced, one source of truth) |
| KG query interface | ✅ | `src/chie/methods/query.cljk` — funders-of / compute-suppliers-of / governed-by / rounds-of / subsidiaries / concentration-in / opening-worklist; reuses the analyze integral (one source of truth) |
| Integrity / charter gate | ✅ | `src/chie/methods/verify.cljk` — one self-audit: struct + kind/edge validity + endpoint resolution + load∈[0,1] + G2 (public-role-only) + G4 (forbidden-token scan) + G5 sourcing + schema drift; adversarial cases test-caught |
| edn-native manifest | ✅ | `manifest.edn` (kotoba/edn-native canonical manifest — gates / methods / cells / bridge / tests) alongside `wire/manifest.jsonld` |
| Tests | ✅ | 13 suites · **69 tests / 227 assertions** green (`kbb -M:test`) |
| Charter gates G1–G5 | ✅ | test-enforced: open→0 (G1), inbound-integral (G2), representative-only (G5), no-trade/no-score (G4) |
| Cross-actor bridge | ✅ (declared) | `:bridge` → kanjō/kabuto/handotai/kasa/kenkyusha/keizu/kosatsu/abaki |
| **常駐化 (resident heartbeat)** | ✅ R1 | `src/chie/methods/autorun.cljk` + `src/chie/cell.cljk` (`fire`) → content-addressed Datom tx on append-only kotoba commit-DAG (`verify-chain` tamper-evident, resume-safe) + Murakumo digest in the summary; registered `ChieHeartbeatCell` in cell-runner `cells.edn` (node gad, cron `37 * * * *`, healthz 13082) |
| Live ingest | 🟡 R2 — offline leg done (G7) | `ingest.cljc` offline fixture + G7 gate landed; the LIVE network fetch (regulator texts / disclosed rounds / Wikidata) is the Council+operator step |
| WASM (pywasm/componentize) | ⏳ R2 | clj source is the pywasm target; build = operator step |

## Roadmap (loop targets)

- **R1 — 常駐化** ✅ (this iteration): `autorun.cljc` heartbeat → analyze → content-addressed
  Datom tx appended to the append-only kotoba commit-DAG (`verify-chain` tamper-evident,
  resume-safe; `cell.cljc` `fire` is the runner entry). `ChieHeartbeatCell` registered in the
  cell-runner `cells.edn` (node gad, cron `37 * * * *`, healthz 13082).
- **R1 — Murakumo digest** ✅: `digest.cljc` template-digest + Murakumo-only `narrate`
  (fail-open) wired into the heartbeat summary.
- **R1 — coverage growth** ✅: 39→53 nodes / 52 縁; added `:ai.invest/round` (disclosed
  rounds) + `:ai.asset/compute` (clusters → kasa) + labs/funders/policy — **all 11 kinds, 8
  edge kinds, 4 axes now covered**. _Next: structured round amounts + planet-scale ingest (R2)._
- **R2 — live leg** 🟡: offline `ingest.cljc` (disclosed fixture → `:authoritative` upgrade +
  `:ai/round-amount-usd` + `:en/disclosed-src`) + G7 refusal landed. _Next: the real network
  fetch behind the G7 gate (kanjō pattern) + per-tx provenance + exactly-once cursor._

## Invariants the suite locks

1. open accumulator → opening-priority 0 (G1, not a winner-rank).
2. concentration = integral of incident inbound 縁 (G2, no stored score).
3. seed is 100% `:representative`; gaps named, never fabricated (G5).
4. `:trade` / `:forecast` / `:ai/score` never appear in the emitted Datom log (G4).
5. emit is deterministic (byte-identical for identical input).
