# chie 智慧 — AI-ecosystem Knowledge Graph mirror

Standalone actor repository. EDN under `manifest.edn`, `data/`, and
`kotoba.app.edn` is canonical; external JSON-LD is isolated under `wire/`.
Runtime and tests live under `src/chie/` and `test/chie/`.

**ADR-2606171200** · 🟢 R1+ · clj-native (`.cljc`) · kotoba/Datom-native.

chie is the **AI sibling** of the power-mirror lineage (tsumugi / keizu / kabuto / kanjō /
kosatsu). It weaves the AI ecosystem — **labs, companies, research bodies, standards bodies,
funders, states, public-role persons, investment rounds, policy instruments, models** — and
the **縁 (edges)** between them into the kotoba Datom log, then runs an **edge-primary
取-concentration** pass over four axes (**compute · capital · talent · policy**) **routed to
OPENING** (open-weights / open-compute / anti-monopoly).

It closes the roster gap where the AI ecosystem (有力者・企業・組織・投資・政策) had **no
unified EDN/Clojure actor** — only scattered fragments (tsumugi power, kabuto supply, kanjō
financials, handotai/kasa hardware, kenkyusha research, `*-compat` API facades).

## The inversion (G1)

chie is **not a winner-ranking**. `:bond/opening-priority` = Σ inbound accumulation ×
**(1 − openness)** — an **open** accumulator (open-weights / open-compute / public standard)
scores **0** even when it accumulates heavily. The map points at *opening the concentration*,
never at "who will win". chie does not grade capability, forecast, or give investment advice,
and **never trades** (`:trade` / `:forecast` are unrepresentable).

## Pipeline

```
seed (kotoba EDN) → analyze (4-axis 取-concentration, on-read) → OPENING priority
                  → datom_emit (EAVT GROUND :add + DERIVED transient)
                  → coverage_report (sourcing honesty + gap worklist)
                  → autorun heartbeat (content-addressed commit-DAG, resume-safe) ── 常駐化
                  → digest (Murakumo-only narration, fail-open template)
                  → ingest (DISCLOSED rounds + policy → :authoritative, G7-gated)
                  → query (funders-of / governed-by / opening-worklist / …)
                  → verify (one self-audit: struct + G2 + G4 + G5 + schema drift)
```

## Run

```bash
# from repo root (bb.edn classpath roots 20-actors)
kbb -M:test:actors                       # auto-discovers all 10 chie suites (53 tests / 165 assertions)

# validated ingest into the root kotoba Datom log
kbb -M:kotoba:ingest 00-contracts/schemas/ai-ecosystem-ontology.kotoba.edn \
                 data/seed.edn --validate
kbb -M:kotoba:roster-report | grep chie  # chie on the roster — 0 undeclared / 0 violations
```

## Files

| Path | Role |
|---|---|
| `manifest.edn` / `wire/manifest.jsonld` | actor manifest (edn-native + JSON-LD) |
| `data/schema/ontology.edn` | rich ontology (axes / forbidden set / bridge) |
| `00-contracts/schemas/ai-ecosystem-ontology.kotoba.edn` | db/ident vocab (root kotoba ingest) |
| `data/seed.edn` | 53-node representative seed (all kinds/edges/axes) |
| `data/ingest/*.fixture.edn` | DISCLOSED-source fixtures (rounds + policy, official URLs) |
| `src/chie/methods/*.cljc` | analyze · datom_emit · coverage_report · autorun · digest · ingest · query · verify |
| `cell.cljc` | cell-runner entry (`ChieHeartbeatCell`, node gad, cron `37 * * * *`) |
| `AGENTS.md` / `MATURITY.md` | gates + scorecard |

## Gates

G1 OPENING-map-not-winner-rank · G2 edge-primary + public-role-only · G3 non-adjudicating ·
G4 never-trades / never-forecasts (unrepresentable) · G5 sourcing-honesty · G6 Murakumo-only ·
G7 live-ingest Council+operator-gated. See `AGENTS.md` for the full text.

## Cross-links

chie **references**, never duplicates: financials → kanjō · supply → kabuto · silicon →
handotai · compute capacity → kasa · research → kenkyusha · gov power → keizu · designations →
kosatsu · antitrust → abaki. It observes the AI field; it does not adjudicate, target, grade, or trade.
