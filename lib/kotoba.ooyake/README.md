# ooyake 公 — World Government Atlas

> A civic wayfinding map of every government on Earth — **not** the government.

`did:web:ooyake.etzhayyim.com` · Tier-B · ADR-2606021600 · **R1 — real verified data, every tier**

ooyake is the kotoba-Datomic-native **structural atlas** of public administration:
supranational → country → region → prefecture → municipality/ward → ministry (省)
→ agency (庁) → bureau (局) → division (課) → section → **窓口**.

**What is actually in the atlas today** (measured 2026-08-07 — the entity
counts, not the intent):

| entity | count | reach |
|---|---|---|
| `:gov.unit` | **7,135** | ministry 1,642 · agency 1,050 · subdivision 3,580 · court 206 · country 193 · legislature 186 · cabinet 129 · supranational 99 |
| `:gov.address` | **7,088** | essentially 1:1 with units |
| `:gov.procedure` | **158** | across 51 owner units, **all `:unverified-seed`** |
| `:gov.form` | **6** | 1 unit |
| `:gov.window` | **4** | 2 units |
| `:gov.bpmn` | **4** | 0 units linked |

**This is an atlas of organizations and their addresses.** It is not yet an
atlas of counters, forms, procedures or process models — those exist as
*seeds*, three orders of magnitude behind the unit tier, and none of them
are verified. Read the counts above before building on 手続き/窓口/書式/BPMN;
an earlier version of this section listed them as if each unit carried them,
which the data does not support.

**Executable procedure semantics live elsewhere.** A `:gov.procedure` seed
records who owns a procedure and what documents it needs; it carries **no
deadline, no lapse effect and no formal-review items**, so it cannot answer
"is this late, and what happens now". That layer is
[`kotoba-lang/tetsuzuki`](https://github.com/kotoba-lang/tetsuzuki) (general
administrative procedure) and [`senkyo`](https://github.com/kotoba-lang/senkyo)
(elections); `tetsuzuki.ooyake` copies these seeds without upgrading them,
and they deliberately fail its conformance check until a statutory basis is
confirmed.

**The municipal tier is not populated.** `subdivision` is ADM1
(prefectures/states). Below it the atlas holds **1 prefecture-level and
1 ward-level unit** — city/town/village and their 窓口 are not seeded.

It is the single read-side SSoT that the other government-facing actors consume:

| Actor | Uses ooyake for |
|---|---|
| **toritsugi** 取次 | which 窓口 / 所管 / 書式 a citizen procedure routes to (delivery) |
| **danjo** 弾正 | the canonical unit list to cross-reference open-data against |
| **kanae** 鼎 | the units to render fiscal flows over |
| **tsumugi** 紡ぎ | reconciling a unit to its `:organism` 縁/取 karma node |
| **himotoki** 繙き | which authority + 窓口 to file a 開示請求 / FOIA against |

## Posture

An **observational mirror + civic wayfinding map** — like tsumugi ("accountability
map, never a target-list") and watatsuna ("resilience map, never a target-list").

- Per-unit atlas DIDs (`did:web:etzhayyim.com:gov:<iso3>:...`) are etzhayyim
  **mirror records** of real public bodies. They never claim to BE the
  government, never act as an official channel (G3, §2(c)).
- **Read-only**: ooyake catalogs. Filing/submitting is toritsugi (gated);
  auditing is danjo. ooyake does neither (G9).
- Civic wayfinding only — never an attack-surface map of the state (G10).

## Coverage (real data, 2026-06-04)

**~6,535 `:gov.unit` rows across ~190 jurisdictions, all `:authoritative` /
`:maintainer-verified`** with an independently-verified Wikidata QID and (where
recorded) the body's own official URL. Spans every tier:

| Tier / branch | What | ~count |
|---|---|---|
| supranational | UN system + major IGOs (intergovernmental) | 96 |
| country | current UN member states | 192 |
| subnational | first-level admin divisions (states/provinces/regions) | 3,599 |
| legislative | national legislatures | 186 |
| judicial | supreme/highest courts | 144 |
| executive | 18 ministry types (finance/foreign/defense/interior/health/justice/education/…) | ~1,850 |
| independent | central banks (158) + audit / ombudsman / electoral / NHRI / anti-corruption / data-protection / competition / financial-regulator / statistics | ~420 |

Plus **~5,693 `:gov.address`** (4,521 with precise lat/lon: national-body HQs +
subnational seats + national capitals) → a derivable world-government **GeoJSON**.

Honest gaps: a few categories are Wikidata-typing-thin (water/industry/competition);
microstates carry fewer bodies; some bodies are sub-national mis-typings retained by
the one-per-country dedup. See [`MATURITY.md`](MATURITY.md) (per-iteration record).

## Layout

```

├── manifest.jsonld              # DID manifest + cells + gates + non-goals
├── AGENTS.md / README.md / MATURITY.md
├── registry/                    # ~30 gov-units*.edn (the canonical EDN data)
│   ├── gov-officeholders.*.edn      # 公人 — current public office holders, keyed to :gov.unit/id
│   └── gov-officeholders.schema.edn # :gov.person/* attribute declarations (Datomic/DataScript)
│   ├── gov-units.seed.edn / gov-units.jp-central.seed.edn   # JP backbone
│   ├── gov-units.g20*.edn       # G20 countries + finance ministries + central banks
│   ├── gov-units.world-*.edn    # world countries / ministries / legislatures / courts / central banks
│   ├── gov-units.oversight-*.edn# audit/ombudsman/electoral/NHRI/anticorruption/… /statistics/revenue
│   ├── gov-units.adm1-*.edn      # first-level subdivisions (5 continent files) + adm1-coords
│   ├── gov-units.intergov.edn / gov-units.capitals.edn / gov-units.hq-locations*.edn
│   └── authority-reference.edn  # reconcile-demo fixture
├── scripts/                     # check_seed_integrity · atlas_summary · coverage_matrix
│   │                            #   · world_coverage · g20_coverage · reconcile · export_geojson
├── cells/reconcile/             # ReconcileCell + tests (incl. integrity-guard self-tests)
├── cells/world_model/           # WorldModelCell — ooyake↔tsumugi cross-actor reconcile + tests
├── deploy/run_tests.sh          # offline gate runner (integrity + coverage + reconcile + …)
└── wire/viz/
    ├── gov-atlas.geojson         # 4,521-feature world-government map (generated)
    └── gov-atlas-map.htm         # self-contained browser viewer (no CDN/tiles)

00-contracts/schemas/gov-atlas-ontology.kotoba.edn   # :gov.* ontology (level/branch enums)
00-contracts/lexicons/com/etzhayyim/ooyake/*.json    # XRPC lexicons (read-only)
90-docs/adr/2606021600-ooyake-world-government-atlas-tier-b-actor-r0.md
```

## Tooling (all offline, `bash deploy/run_tests.sh`)

- `scripts/check_seed_integrity.py` — guards QID uniqueness/format, the
  level/branch/sourcing enums, G5 provenance, and address→unit + parent refs.
- `scripts/atlas_summary.py` — by level / branch / sourcing / jurisdiction.
- `scripts/coverage_matrix.py` — per-country presence across 35 functional categories.
- `scripts/export_geojson.py` — derive `wire/viz/gov-atlas.geojson` from the registry.
- `scripts/world_model.py` — cross-actor **world-model reconcile**: join the
  structural atlas (`:gov.unit/*`) to tsumugi's karma graph (`:organism/*`) over the
  shared `:gov.unit/organism` id-space; `--edn out/` writes the proposed world-model
  artifact. Offline, read-side proposal (G9) — see "World model" below.
- open `wire/viz/gov-atlas-map.htm` in a browser to explore the map.

## World model (cross-actor reconcile)

ooyake is **structure**; tsumugi (`:organism/* + :en/*`) is **karma** (縁/取). The
two are joined per-entity by the `:gov.unit/organism` ref — the same public body
seen from both graphs. `cells/world_model/` performs that reconcile OFFLINE and
deterministically, classifying every **power-bearing** unit (country / supranational
/ cabinet / ministry / agency / bureau / legislature / court — local 窓口/ward/
division are **excluded by construction**, civic-wayfinding never a target-list) as:

- **confirmed** — explicit `:gov.unit/organism` whose target organism exists
  (today: `gov.jpn.meti → org.state.jp.meti`);
- **derived** — derived organism id (`gov.X → org.gov.X`) already in the karma graph;
- **dangling** — explicit link with a MISSING target (G5 flag);
- **proposed** — power-bearing, no counterpart → a `:latent` / `:representative`
  organism stub + proposed link written to `out/world-model.kotoba.edn`.

It also flags **orphan** governmental organisms (in the karma graph, absent from the
atlas) and counts non-gov organisms (corps/roles → kabuto/kanjo/tsumugi, correctly
out of atlas scope). It is a **read-side proposal**: it never mutates a committed
seed — applying a proposed link is a separate operator-gated step (`mode="live"`
raises). Run: `python3 scripts/world_model.py --edn out/`.

Beyond matched nodes, the world model resolves and persists the actual cross-graph
join:

- **Government stewardship paths** — reconciled gov-unit → its organism →
  `:tends`/`:custodies` 縁 → entity. The report's `government_stewardship` view + the
  `:government-stewardship` block in the artifact (e.g. `gov.eu --:tends--> Apple`,
  `gov.usa.sec --:tends--> NVIDIA`). 9 reconciled gov nodes wire **20 paths** today.
- **Bidirectional query** — `regulators_of(entity)` (reverse: who governs X?) and
  `stewarded_entities_of(gov_unit)` (forward). Consumed by tsumugi/danjo/kanae via
  `deploy/consumers_example.py::world_model_regulators`; CLI:
  `scripts/world_model.py --entity org.corp.us.apple` → `{gov.eu, gov.usa.sec}`.
- **kotoba persistence** — `deploy/ingest_world_model.py` projects the reconciled,
  factual model (NOT the proposals) into the canonical named graph **`world-model-v1`**
  (`world.gov` entities with `world/organism` + `world/stewards` relations). Dry-run
  by default; live ingest operator-gated (`KOTOBA_TOKEN`); never auto-seals.
- **Drift-lock** — `cells/world_model/test_consistency.py` binds the registry links,
  tsumugi seed, coverage gate, manifest, ingest graph name, and runner to one SSoT.

The 9 confirmed links today (METI, FSA, BOJ, SEC, Fed, EU, UK CMA, US DOJ, JFTC) are
all publicly-documented regulator→entity ties; the rest of the atlas is honestly
`:proposed`/`:representative`. All offline + gated; `bash deploy/run_tests.sh`.

## Query surface (read-only XRPC)

- `com.etzhayyim.ooyake.getUnit` — resolve a unit + its children/addresses/windows
- `com.etzhayyim.ooyake.resolvePath` — resolve a dotted path / atlas DID to a unit
- `com.etzhayyim.ooyake.findService` — *"where do I do procedure X near me?"* →
  procedure + window + address (the citizen wayfinding query)
- `com.etzhayyim.ooyake.searchUnits` — text/geo search; backs civic search at
  `etzhayyim.com` (`/actors` kotoba-wasm search surfaces gov units at R1)

## Status

**R1 — real verified data, committed.** The registry holds ~6,535 maintainer-verified
units (real Wikidata QIDs, body-own provenance) across every governance tier, with a
derivable GeoJSON map. What remains **gated** (operator/Council, NOT done here):

- **Live kotoba ingest** of the registry into the `gov-atlas-v1` Datom graph — needs an
  operator token + node (`KOTOBA_TOKEN`).
- **Publishing** national `:authoritative` rows to `/.well-known/gov-units.json` — the
  Council-Lv6+ / bootstrap-attestation gate (`validate_atlas.py` check #5 currently
  admits only the JP prefecture/city backbone as published-authoritative).

i.e. this is the committed registry **record** of real data; ingest + public
publication are the separate operator/Council steps. See [`MATURITY.md`](MATURITY.md)
for the full per-iteration build log.
