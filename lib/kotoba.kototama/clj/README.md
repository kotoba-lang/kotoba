# kototama

Functional UNSPSC organism actors on the Clojure substrate — **one framework,
18,342 living, individuated actors** (kotoba Datom + Clojure + langgraph-clj).

This is the extraction/migration target for the 18,343 Python `c<code>.py`
LangGraph agents that lived in `etzhayyim/kotoba` (ADR-2606131645). The Python
fleet was 90% hollow template stubs; this replaces them with a single functional
organism framework + a per-code data table, so **every** UNSPSC code is a real,
commodity-specific, deployable actor — coverage preserved (18,342), stubs gone.

## kototama as the common organism/cell library (`kototama.*`)

Beyond the UNSPSC fleet, **kototama is the distilled common library for building
CELLS and ARTIFICIAL ORGANISMS** on kotoba — a subset of the kotodama framework +
the ibuki organism pattern, dependency-free `.cljc` so it runs on bb / JVM **and**
inside the kototama Rust→WASM runtime. The UNSPSC fleet (`kototama.unspsc.*`) is
its first consumer; external actors (e.g. etzhayyim **kyoninka 許認可**, which
autonomously posts its robotaxi-permitting readiness digest) are the next.

| ns | role | distilled from |
|---|---|---|
| `kototama.kotoba` | append-only, content-addressed Datom log (connect/transact/db/as-of/verify-chain) — the DB | `etzhayyim.kotoba.engine` + `ibuki.methods.datoms` |
| `kototama.cell` | `defcell` — a cell is a pure `solve : state → state` | kotodama Pregel cell |
| `kototama.life` | joucho (mood) + metabolism (Φ/η/surprise), folded off the log | `ibuki organism.cljc` / `metabolism.cljc` |
| `kototama.gates` | charter membrane: `may-draft?` / §2 catastrophe `scan` / `may-actuate?` | kototama `ACTOR_PRELUDE` / `gates.cljc` |
| `kototama.leash` | revocable member CACAO capability (present-only; `write-author`) | ibuki delegation (ADR-2606111400) |
| `kototama.emit` | member-signed post envelope → app-aozora / com-etzhayyim (never `:published`) | ibuki drainer / member-submit |
| `kototama.organism` | the heartbeat: replay→perceive→feel→decide→narrate→act→persist; `beat`/`autorun` | ibuki autorun + organism.cljc |
| `kototama.core` | thin re-exports of the common path | — |

Design invariants (all preserved by the lib): **kotoba Datom log = first-class
state**; content-addressed + tamper-evident (`verify-chain`) + idempotent-by-
content (crash-resume byte-identical); **no-server-key** (present-only leash,
never signs); **publication ≠ actuation** (autonomous posting is on by default
per the 種をまく doctrine, but high-stakes actuation stays behind `may-actuate?`);
§2 content scan before every emit; no wall-clock (caller passes `now`/`created-at`
→ replay-safe). `kototama` (Rust) compiles these `.cljc` to WASM (`compile_actor`);
roadmap Phase 4 extracts this lib to its own home.

```clojure
;; build an organism that autonomously posts under a member's revocable leash
(require '[kototama.core :as k])
(def o (k/make-organism {:id "did:web:…:kyoninka" :leash (k/make-leash member-cacao)
                         :decide (fn [ctx] {:events [:event/served] :act? true
                                            :post-text (digest ctx)})}))
(k/beat o {:now 1782604800 :created-at "2026-06-28T00:00:00Z"})
;; → {:mood :content :envelope {:status :dry-run :writeAuthor "did:plc:…" …} …}
```

Run the common-lib tests: `kbb --classpath src:test -e "(require 'kototama.core-test)(kototama.core-test/-main)"` (10 tests / 36 assertions).


## Design

- **Coverage stays, files collapse.** Actor *count* is unchanged (18,342); only
  the hand-written `.py` files collapse to `framework + data`.
- **Functional, not stub.** Every code does real, input-validating work:
  - `kototama.unspsc.capability` — domain logic generalized from the ~1,655
    bespoke agents into segment capabilities + universal procurement baseline +
    risk-tag-driven checks. No code is a no-op (empty input is always rejected).
  - `kototama.unspsc.organism` — a langgraph-clj graph `validate → reason → emit`
    per taxon; Murakumo-grounded reasoning (fail-open template, Charter-compliant
    Murakumo-only inference).
  - `kototama.unspsc.taxonomy` — the per-code data table (`resources/unspsc-taxonomy.edn`).
  - `kototama.unspsc.life` — the organic axis: joucho (mood) emerges from a fold
    over each actor's lived event history; heartbeat cadence gates outward acts.
- **kotoba Datom state.** Actor state persists via the langgraph checkpointer over
  a Datomic-shaped log — `langchain.db` in-process for dev, `langchain.kotoba-db`
  (kotoba-server XRPC) for the distributed kotoba Datom backend. Each actor accrues
  an as-of history on a stable thread (`unspsc-<code>`).
- **Runtime contract preserved** from the Python agents:
  `invoke(input) -> {:result {:code :title :segment :did :ok ...} :log [..]}`,
  DID `did:web:etzhayyim.com:actor:c<code>`.

## Layout

```
src/kototama/unspsc/
  build_taxonomy.clj   # registry ⨝ enrichment → resources/unspsc-taxonomy.edn
  taxonomy.clj         # load + query the data table
  capability.clj       # domain capability library (the functional core)
  organism.clj         # the langgraph-clj actor framework + Murakumo model
  life.clj             # joucho / heartbeat (the organic axis)
resources/unspsc-taxonomy.edn   # 18,342 codes (generated)
test/kototama/unspsc/organism_test.clj
```

## Use

```bash
# (re)build the taxonomy data table from the etzhayyim/root sources
kbb -M:build-taxonomy

# run the pilot tests
kbb -X:test
```

```clojure
(require '[kototama.unspsc.organism :as org])
;; nil model → deterministic template reasoning; inject (org/murakumo-model …) in prod
(org/run-actor "10101500"
               {:quantity 12 :unit "head"
                :source_country "JP" :animal_health_certificate "AHC-1"
                :grading_standards "A5" :health_data {:certified true}
                :quarantine_status "cleared" :cold_chain "2C" :provenance "farm-x"})
;; => {:code "10101500" :title "Live Animal" :did "did:web:…:c10101500"
;;     :domain :live-plant-and-animal :ok true :checks [...] :reasoning "…"}
```

## Status

- **Phase 1 (this repo)**: functional framework + capability library + 18,342-code
  taxonomy + pilot — **7 tests / 65 assertions green**.
- Phase 2: enrich all 18,342 with per-commodity spec/capability (Murakumo data gen).
- Phase 3: instantiate + deploy the fleet on the Murakumo cluster (kotoba Datom).
- Phase 4: extract to `etzhayyim/kototama`; root drops the kotoba submodule.

See ADR-2606131645 (`etzhayyim/root/90-docs/adr/`). Apache 2.0 + etzhayyim Charter
Compliance Rider v3.1.
