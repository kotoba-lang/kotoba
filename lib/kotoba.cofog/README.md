# kotoba-cofog

COFOG (UN Classification of the Functions of Government) registry for
kotoba-lang and itonami open businesses.

This repository maps COFOG-coded government functions to the technology
capabilities needed to run an independent operator business against that
function -- the government-function-classification counterpart to
`kotoba-industry` (ISIC-coded businesses) and `kotoba-occupation`
(ISCO-08-coded occupations).

## Contract

```clojure
(require '[kotoba.cofog :as cofog])

(cofog/get-cofog "04.5")
(cofog/required-technologies "05.1")
(cofog/readiness "06.3" #{:robotics :telemetry :dmn :bpmn :audit-ledger})
```

## Portable, and how the registry gets compiled in

`kotoba.cofog` is `.cljc` and touches **no file at runtime**. The registry
lives in `resources/kotoba/cofog/registry.edn` — that is still the source of
truth and the only thing to edit — and `tools/gen-embedded.cljk` projects it
into the generated `src/kotoba/cofog/embedded.cljk`, which is what the
library reads.

```sh
kbb --backend sci tools/gen-embedded.cljk           # after editing the EDN
kbb --backend sci tools/gen-embedded.cljk --check   # exit 1 if the projection is stale

kbb -M:test                                   # JVM
kbb --backend sci --classpath src:test:<technology/src> test/run_portable.cljk   # ClojureScript
kbb --backend sci tools/mutate.cljk                             # prove the suite can fail
```

`io/resource` has no portable equivalent, and reading `resources/<path>`
relative to the working directory is right only while this library is the
root project — measured wrong on 2026-08-18, when `kotoba-lang/technology`
briefly worked that way and returned nil for all 159 of `kotoba.iso3166`'s
assertions under nbb. This registry exists to be depended on, so it is
compiled in instead.

## Layers

- business: customer-facing open COFOG blueprint
- cofog: COFOG-coded operating domain (what public function is served)
- technology: reusable kotoba-lang capability stack
- implementation: concrete repos, services and operators

ISIC classifies what a *business* produces; ISCO classifies what a *worker*
does; COFOG classifies what *government function* a service serves.
`cloud-itonami-cofog-{code}` publishes forkable OSS operator businesses that
serve a government function under contract or as a licensed civic-tech
vendor -- e.g. municipal infrastructure inspection, waste collection -- NOT
the government itself (see `matsurigoto`, etzhayyim/root, for the sovereign
e-government statecraft use of the same COFOG backbone; this registry is the
*commercial operator* counterpart, structurally separate).

Divisions (`01`..`10`) are parent/queryable nodes only, not independently
blueprint-eligible -- mirroring how `kotoba-occupation` treats ISCO-08 major
groups. Groups (`01.1`, `04.5`, ...) are the blueprint-eligible level.

## Current COFOG Blueprints

| COFOG | Function | Blueprint | Required technology |
|---:|---|---|---|
| 03.2 | Fire-protection services | Independent Fire-Risk Inspection Robotics | robotics, telemetry, forms, dmn, bpmn, audit-ledger |
| 04.5 | Transport | Independent Road & Bridge Inspection Robotics | robotics, telemetry, forms, dmn, bpmn, audit-ledger |
| 05.1 | Waste management | Independent Municipal Waste Collection Robotics | robotics, telemetry, optimization, bpmn, audit-ledger |
| 06.3 | Water supply | Independent Water Infrastructure Leak-Detection Robotics | robotics, telemetry, dmn, bpmn, audit-ledger |
| 07.4 | Public health services | Independent Community Vector-Control & Environmental Health Monitoring | robotics, telemetry, identity, dmn, bpmn, audit-ledger |

5 representative groups across 5 divisions (economic affairs / environmental
protection / housing & amenities / health / public order) are `:maturity
:blueprint`. The remaining 74 COFOG entries (10 divisions + 64 groups) are
registered at `:maturity :spec` (registry-only stub, full 79/79 COFOG
coverage) for future promotion, following the same `:spec` -> `:blueprint`
-> `:implemented` path `kotoba-industry` / `kotoba-occupation` use.

Division/group English + Japanese labels are reused verbatim from
`matsurigoto`'s authoritative COFOG backbone (etzhayyim/root,
`20-actors/matsurigoto/data/cofog-standard.kotoba.edn`, itself sourced from
UN Statistics Division / OECD-Eurostat COFOG / IMF GFSM 2014), not
re-derived.

## Test

```bash
kbb -M:test
```
