# kotoba-unspsc

UNSPSC (United Nations Standard Products and Services Code) SEGMENT-level
registry for kotoba-lang and itonami open businesses.

This repository maps UNSPSC-segment-coded commodity/service domains to the
technology capabilities needed to run an independent operator business
sourcing, servicing or refurbishing that segment -- the
product/service-commodity-classification counterpart to `kotoba-industry`
(ISIC), `kotoba-occupation` (ISCO-08) and `kotoba-cofog` (COFOG).

**Coarser than commodity level, by design.** UNSPSC has ~150,000 commodity
codes at full depth. This registry works at the **segment** (2-digit)
level -- ~53 segments -- so that "1 segment = 1 independent operator
business" stays a coherent unit, the same choice `kotoba-industry` makes at
ISIC class level rather than trying to publish a blueprint per SKU.

## Provenance note (read before trusting a segment number/title)

Unlike `kotoba-cofog`, which mirrors an authoritative source file
(`matsurigoto`'s COFOG data) verbatim, this segment list is drawn from
general knowledge of the UNSPSC segment taxonomy structure, **not copied
from a verified official UNSPSC codeset file present in this workspace**.
Verify segment numbers/titles against the official UNSPSC codeset
(unspsc.org / GS1 US) before relying on this registry for anything beyond a
structural starting point.

**This is NOT the workspace's authoritative UNSPSC data.** The live,
authoritative, commodity-level UNSPSC surface is the clj `unspsc` actor
(etzhayyim/root, `20-actors/unspsc`, an 18,342-code data table, per
ADR-2606172100 -- which retired an earlier 18,343-file-per-code Python
fleet, ADR-2605171300). This registry does not duplicate or supersede that
data; it is a separate, coarser-grained registry purpose-built for the
`cloud-itonami` open-business-blueprint pattern.

## Contract

```clojure
(require '[kotoba.unspsc :as unspsc])

(unspsc/get-segment "27")
(unspsc/required-technologies "43")
(unspsc/readiness "73" #{:robotics :telemetry :optimization :bpmn :audit-ledger})
```

## Current UNSPSC Blueprints

| Segment | Name | Blueprint | Required technology |
|---:|---|---|---|
| 10 | Live Plant and Animal Material and Accessories and Supplies | Independent Urban Apiary & Pollinator Services | robotics, telemetry, optimization, audit-ledger |
| 27 | Tools and General Machinery | Independent Tool Fleet Rental & Maintenance Robotics | robotics, telemetry, optimization, bpmn, audit-ledger |
| 39 | Electrical Systems and Lighting and Components and Accessories and Supplies | Independent Solar & EV-Charging Install & Diagnostics | robotics, telemetry, forms, dmn, bpmn, audit-ledger |
| 43 | Information Technology Broadcasting and Telecommunications | Independent IT Asset Recovery & E-Waste Refurbishment Robotics | robotics, identity, telemetry, audit-ledger |
| 73 | Industrial Production and Manufacturing Services | Independent Industrial Cleaning & Certification Robotics | robotics, telemetry, optimization, bpmn, audit-ledger |

5 representative segments are `:maturity :blueprint`. The remaining 48
segments are registered at `:maturity :spec` (registry-only stub) for
future promotion, following the same `:spec` -> `:blueprint` ->
`:implemented` path `kotoba-industry` / `kotoba-occupation` / `kotoba-cofog`
use.

## Portable, and how the registry gets compiled in

`kotoba.unspsc` is `.cljc` and touches **no file at runtime** (so is
`kotoba.unspsc.product`, which always was). The registry lives in
`resources/kotoba/unspsc/registry.edn` — that is still the source of truth
and the only thing to edit — and `tools/gen-embedded.cljk` projects it into
the generated `src/kotoba/unspsc/embedded.cljk`, which is what the library
reads.

`io/resource` has no portable equivalent, and reading `resources/<path>`
relative to the working directory is right only while this library is the
root project — measured wrong on 2026-08-18, when `kotoba-lang/technology`
briefly worked that way and returned nil for all 159 of `kotoba.iso3166`'s
assertions under nbb. This registry exists to be depended on, so it is
compiled in instead.

## Test

```bash
kbb -M:test                       # JVM

# ClojureScript, no build step. <technology/src> is the checkout of
# kotoba-lang/technology named in deps.edn.
kbb --backend sci --classpath src:test:<technology/src> test/run_portable.cljk

kbb --backend sci tools/gen-embedded.cljk           # after editing the EDN
kbb --backend sci tools/gen-embedded.cljk --check   # exit 1 if the projection is stale
kbb --backend sci tools/mutate.cljk                 # prove the suite can fail
```
