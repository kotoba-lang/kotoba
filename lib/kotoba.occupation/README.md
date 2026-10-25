# kotoba-occupation

Occupation registry for kotoba-lang and itonami open businesses.

This repository maps ISCO-08-coded sole-proprietor occupations to the
technology capabilities they need in order to operate. `cloud-itonami-isco-*`
uses this to move from a published occupation blueprint to an executable
operating stack — the occupation-classification counterpart to
`kotoba-industry` (ISIC-coded businesses).

## Contract

```clojure
(require '[kotoba.occupation :as occupation])

(occupation/get-occupation "2221")
(occupation/required-technologies "6112")
(occupation/readiness "9312" #{:forms :telemetry :audit-ledger :bpmn :dmn})
```

## Portable, and how the registry gets compiled in

`kotoba.occupation` is `.cljc` and touches **no file at runtime** and calls
**no host hash** (so is `kotoba.occupation.wave`, which always was). The
registry lives in `resources/kotoba/occupation/registry.edn` — that is still
the source of truth and the only thing to edit — and `tools/gen-embedded.cljk`
projects it into the generated `src/kotoba/occupation/embedded.cljk`, which
is what the library reads.

`io/resource` has no portable equivalent, and reading `resources/<path>`
relative to the working directory is right only while this library is the
root project — measured wrong on 2026-08-18, when `kotoba-lang/technology`
briefly worked that way and returned nil for all 159 of `kotoba.iso3166`'s
assertions under nbb. This registry exists to be depended on, so it is
compiled in instead.

`java.security.MessageDigest`, which minted the deterministic draft ids, is
replaced by `kotoba-lang/org-nist-sha2` — the workspace's portable `.cljc`
SHA-256 — rather than a `:cljs` reader conditional over `node:crypto`, which
would work under nbb and not in a browser. **The ids are unchanged**:
`gap-1321-1a37fe18cbe0da38` is what the JVM produced before the change, what
both runtimes produce now, and what `shasum -a 256` produces over the same
bytes. That constant is pinned in the suite.

```bash
kbb -M:test                       # JVM

# ClojureScript, no build step. The two extra classpath entries are the
# checkouts of the git deps named in deps.edn.
kbb --backend sci --classpath src:test:<technology/src>:<org-nist-sha2/src> \
    test/run_portable.cljk

kbb --backend sci tools/gen-embedded.cljk           # after editing the EDN
kbb --backend sci tools/gen-embedded.cljk --check   # exit 1 if the projection is stale
kbb --backend sci tools/mutate.cljk                 # prove the suite can fail
```

## Layers

- business: customer-facing open occupation blueprint
- occupation: ISCO-08-coded operating domain (what the worker does)
- technology: reusable kotoba-lang capability stack
- implementation: concrete repos, services and operators

ISIC classifies what a *business* produces; ISCO classifies what a *worker*
does. `cloud-itonami-{ISIC}` publishes industry-vertical business blueprints;
`cloud-itonami-isco-{code}` publishes sole-proprietor occupation blueprints
(1 occupation = 1 independent operator). The `isco-` infix in the repo name is
required — ISIC and ISCO-08 unit-group codes overlap numerically, so a bare
`cloud-itonami-{code}` would be ambiguous between the two registries.

## Current ISCO-08 Blueprints

| ISCO-08 | Occupation | Blueprint | Required technology |
|---:|---|---|---|
| 1321 | Manufacturing Managers | Independent Manufacturing Floor Management (**:implemented** — real actor: `manufacturing-floor.store`/`.governor`, 7 tests) | robotics, identity, dmn, bpmn, audit-ledger, telemetry |
| 2221 | Nursing Professionals | Independent Home Nursing Practice (**:implemented** — real actor: `home-nursing.store`/`.governor`, 8 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger, telemetry |
| 3253 | Community Health Workers | Community Health Outreach Practice (**:implemented** — real actor: `community-health.store`/`.governor`, 7 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4321 | Stock Clerks | Independent Warehouse Stock Operations (**:implemented** — real actor: `warehouse-stock.store`/`.governor`, 8 tests) | robotics, forms, telemetry, optimization, audit-ledger, bpmn |
| 5322 | Home-based Personal Care Workers | Independent Home-Based Care Practice (**:implemented** — real actor: `home-care.store`/`.governor`, 7 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger, telemetry |
| 6112 | Market Gardeners and Crop Growers | Independent Market Gardening Operations (**:implemented** — real actor: `market-garden.store`/`.governor`, 7 tests) | robotics, telemetry, optimization, dmn, bpmn, audit-ledger, forms |
| 7126 | Plumbers and Pipe Fitters | Independent Plumbing Practice (**:implemented** — real actor: `plumbing.store`/`.governor`, 7 tests) | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 8332 | Heavy Truck and Lorry Drivers | Independent Freight Driving Operations (**:implemented** — real actor: `freight-driving.store`/`.governor`, 9 tests) | robotics, telemetry, identity, dmn, bpmn, audit-ledger |
| 9312 | Civil Engineering Labourers | Independent Civil Labour Crew (**:implemented** — real actor: `civil-labour.store`/`.governor`, 7 tests) | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 3141 | Life Science Technicians (excluding Medical) | Independent Field & Lab Science Support Practice (**:implemented** — real `langgraph.graph` Actor: `field-lab-science-support.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, telemetry, forms, dmn, bpmn, audit-ledger |
| 5223 | Shop Sales Assistants | Independent Retail Floor Sales Practice (**:implemented** — real actor: `retail-floor.store`/`.governor`, 8 tests) | robotics, forms, telemetry, audit-ledger, bpmn |
| 6210 | Forestry and Related Workers | Independent Forestry Operations (**:implemented** — real actor: `forestry.store`/`.governor`, 7 tests) | robotics, telemetry, forms, dmn, bpmn, audit-ledger |
| 7231 | Motor Vehicle Mechanics and Repairers | Independent Auto Repair Practice (**:implemented** — real actor: `auto-repair.store`/`.governor`, 7 tests) | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 8121 | Metal Processing Plant Operators | Independent Metal Processing Plant Operations (**:implemented** — real actor: `metal-plant.store`/`.governor`, 7 tests) | robotics, telemetry, dmn, bpmn, audit-ledger |
| 9111 | Domestic Cleaners and Helpers | Independent Domestic Cleaning Practice (**:implemented** — real actor: `domestic-cleaning.store`/`.governor`, 8 tests) | robotics, identity, forms, audit-ledger |
| 1120 | Managing Directors and Chief Executives | Independent Small-Business Executive Practice (**:implemented** — real actor: `exec-practice.store`/`.governor`, 8 tests) | robotics, identity, dmn, bpmn, audit-ledger |
| 1212 | Human Resource Managers | Independent HR Management Practice (**:implemented** — real actor: `hr-management.store`/`.governor`, 8 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger, telemetry |
| 2512 | Software Developers | Independent Software Development Studio (**:implemented** — real actor: `dev-studio.store`/`.governor`, 9 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4110 | General Office Clerks | Independent Office Administration Practice (**:implemented** — real actor: `office-admin.store`/`.governor`, 8 tests) | robotics, forms, audit-ledger, bpmn |
| 3213 | Pharmaceutical Technicians and Assistants | Independent Pharmacy Support Practice (**:implemented** — real actor: `pharmacy-support.store`/`.governor`, 7 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 5153 | Building Caretakers | Independent Building Caretaking Practice (**:implemented** — real actor: `building-caretaking.store`/`.governor`, 7 tests) | robotics, forms, telemetry, audit-ledger, bpmn |
| 7411 | Building and Related Electricians | Independent Electrical Practice (**:implemented** — real actor: `electrical-practice.store`/`.governor`, 7 tests) | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 2262 | Pharmacists | Independent Pharmacy Practice (**:implemented** — real actor: `pharmacy-practice.store`/`.governor`, 8 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4222 | Contact Centre Information Clerks | Independent Reception & Contact Practice (**:implemented** — real actor: `reception-contact.store`/`.governor`, 8 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 5311 | Child Care Workers | Independent Child Care Practice (**:implemented** — real actor: `child-care.store`/`.governor`, 8 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 6130 | Mixed Crop and Animal Producers | Independent Mixed Farming Operations (**:implemented** — real `langgraph.graph` Actor: `mixed-farming.actor`/`.advisor`/`.governor`/`.store`, 10 tests — first `cloud-itonami-isco-*` on the full itonami Actor pattern) | robotics, telemetry, optimization, dmn, bpmn, audit-ledger, forms |
| 8160 | Food and Related Products Machine Operators | Independent Food Processing Operations (**:implemented** — real `langgraph.graph` Actor: `food-processing.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, telemetry, dmn, bpmn, audit-ledger |
| 9412 | Kitchen Helpers | Independent Kitchen Support Practice | robotics, forms, audit-ledger |
| 1330 | Information and Communications Technology Services Managers | Independent IT Services Management Practice (**:implemented** — real `langgraph.graph` Actor: `it-services.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 3512 | Information and Communications Technology User Support Technicians | Independent IT Support Practice (**:implemented** — real `langgraph.graph` Actor: `it-support.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 6222 | Inland and Coastal Waters Fishery Workers | Independent Small-Scale Fishery Operations | robotics, telemetry, forms, dmn, bpmn, audit-ledger |
| 7115 | Carpenters and Joiners | Independent Carpentry Practice | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 8342 | Earthmoving and Related Plant Operators | Independent Earthmoving Operations | robotics, telemetry, dmn, bpmn, audit-ledger |
| 9622 | Odd-job Persons | Independent Handyman Practice | robotics, forms, audit-ledger, bpmn |
| 1219 | Business Services and Administration Managers Not Elsewhere Classified | Independent Business Administration Management Practice (**:implemented** — real `langgraph.graph` Actor: `business-admin.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 2411 | Accountants | Independent Accounting Practice (**:implemented** — real `langgraph.graph` Actor: `accounting.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4413 | Coding, Proofreading and Related Clerks | Independent Document Processing Practice (**:implemented** — real `langgraph.graph` Actor: `document-processing.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, audit-ledger |
| 3123 | Construction Supervisors | Independent Construction Supervision Practice (**:implemented** — real `langgraph.graph` Actor: `construction-supervision.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 7212 | Welders and Flame Cutters | Independent Welding Practice | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 9333 | Freight Handlers | Independent Freight Handling Practice | robotics, forms, telemetry, audit-ledger, bpmn |
| 2634 | Psychologists | Independent Psychology Practice (**:implemented** — real `langgraph.graph` Actor: `psychology.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 5120 | Cooks | Independent Culinary Practice (**:implemented** — real `langgraph.graph` Actor: `culinary.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, telemetry, audit-ledger, bpmn |
| 6114 | Mixed Crop Growers | Independent Mixed Crop Growing Operations (**:implemented** — real `langgraph.graph` Actor: `mixed-crop.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, telemetry, optimization, dmn, bpmn, audit-ledger, forms |
| 1349 | Professional Services Managers Not Elsewhere Classified | Independent Professional Services Management Practice (**:implemented** — real `langgraph.graph` Actor: `professional-services.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4131 | Typists and Word Processing Operators | Independent Typing and Transcription Practice (**:implemented** — real `langgraph.graph` Actor: `typing-transcription.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, audit-ledger, bpmn |
| 8189 | Stationary Plant and Machine Operators Not Elsewhere Classified | Independent Stationary Plant Operations | robotics, telemetry, dmn, bpmn, audit-ledger |
| 3339 | Business Services Agents Not Elsewhere Classified | Independent Business Services Agency Practice (**:implemented** — real `langgraph.graph` Actor: `business-services-agency.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 5164 | Pet Groomers and Animal Care Workers | Independent Pet Care Practice (**:implemented** — real `langgraph.graph` Actor: `pet-care.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, telemetry, audit-ledger, bpmn |
| 8172 | Wood Processing Plant Operators | Independent Wood Processing Operations | robotics, telemetry, dmn, bpmn, audit-ledger |
| 2320 | Vocational Education Teachers | Independent Vocational Education Practice (**:implemented** — real `langgraph.graph` Actor: `vocational-education.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4211 | Bank Tellers and Related Clerks | Independent Financial Services Teller Practice (**:implemented** — real `langgraph.graph` Actor: `teller-services.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 5169 | Personal Services Workers Not Elsewhere Classified | Independent Personal Services Practice (**:implemented** — real `langgraph.graph` Actor: `personal-services.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 6221 | Aquaculture Workers | Independent Aquaculture Operations | robotics, telemetry, dmn, bpmn, audit-ledger, forms |
| 7233 | Agricultural and Industrial Machinery Mechanics and Repairers | Independent Farm & Industrial Machinery Repair Practice | robotics, forms, telemetry, dmn, bpmn, audit-ledger |
| 9211 | Crop Farm Labourers | Independent Crop Farm Labour Practice | robotics, telemetry, forms, audit-ledger, bpmn |
| 2166 | Graphic and Multimedia Designers | Independent Graphic Design Studio (**:implemented** — real `langgraph.graph` Actor: `design-studio.actor`/`.advisor`/`.governor`/`.store`) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4229 | Client Information Workers Not Elsewhere Classified | Independent Client Information Services Practice (**:implemented** — real `langgraph.graph` Actor: `client-information.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 8154 | Bleaching, Dyeing and Fabric Cleaning Machine Operators | Independent Fabric Processing Operations | robotics, telemetry, dmn, bpmn, audit-ledger |
| 1412 | Restaurant Managers | Independent Restaurant Management Practice (**:implemented** — real `langgraph.graph` Actor: `restaurant-management.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 3255 | Physiotherapy Technicians and Assistants | Independent Physiotherapy Support Practice (**:implemented** — real `langgraph.graph` Actor: `physiotherapy-support.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 5162 | Companions and Valets | Independent Companion & Valet Practice (**:implemented** — real `langgraph.graph` Actor: `companion-valet.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, audit-ledger, bpmn |
| 2422 | Policy Administration Professionals | Independent Policy Administration Practice (**:implemented** — real `langgraph.graph` Actor: `policy-administration.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4415 | Filing and Copying Clerks | Independent Filing & Copying Practice (**:implemented** — real `langgraph.graph` Actor: `filing-copying.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, audit-ledger |
| 5230 | Cashiers and Ticket Clerks | Independent Cashier & Ticketing Practice (**:implemented** — real `langgraph.graph` Actor: `cashier-ticketing.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 3122 | Manufacturing Supervisors | Independent Manufacturing Supervision Practice (**:implemented** — real `langgraph.graph` Actor: `manufacturing-supervision.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 6111 | Field Crop and Vegetable Growers | Independent Field Crop Growing Operations (**:implemented** — real `langgraph.graph` Actor: `field-crop-growing.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, telemetry, optimization, dmn, bpmn, audit-ledger, forms |
| 8322 | Car, Taxi and Van Drivers | Independent Car & Van Driving Practice | robotics, telemetry, identity, dmn, bpmn, audit-ledger |
| 2144 | Mechanical Engineers | Independent Mechanical Engineering Practice (**:implemented** — real `langgraph.graph` Actor: `mechanical-engineering.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4322 | Production Clerks | Independent Production Clerk Practice (**:implemented** — real `langgraph.graph` Actor: `production-clerking.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, telemetry, audit-ledger, bpmn |
| 5249 | Sales Workers Not Elsewhere Classified | Independent Sales Practice (**:implemented** — real `langgraph.graph` Actor: `general-sales.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 1341 | Child Care Services Managers | Independent Child Care Services Management Practice (**:implemented** — real `langgraph.graph` Actor: `child-care-services.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 6121 | Livestock and Dairy Producers | Independent Livestock & Dairy Operations (**:implemented** — real `langgraph.graph` Actor: `livestock-dairy.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, telemetry, optimization, dmn, bpmn, audit-ledger, forms |
| 7318 | Handicraft Workers in Textile, Leather and Related Materials | Independent Textile & Leather Handicraft Practice | robotics, forms, audit-ledger, bpmn |
| 1439 | Services Managers Not Elsewhere Classified | Independent Services Management Practice (**:implemented** — real `langgraph.graph` Actor: `services-management.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4132 | Data Entry Clerks | Independent Data Entry Practice (**:implemented** — real `langgraph.graph` Actor: `data-entry.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, audit-ledger |
| 8153 | Sewing Machine Operators | Independent Sewing Operations | robotics, telemetry, dmn, bpmn, audit-ledger |
| 2621 | Archivists and Curators | Independent Archival & Curatorial Practice (**:implemented** — real `langgraph.graph` Actor: `archival-curatorial.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 4224 | Hotel Receptionists | Independent Hotel Reception Practice (**:implemented** — real `langgraph.graph` Actor: `hotel-reception.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 7523 | Woodworking Machine Tool Setters and Operators | Independent Woodworking Machine Operations | robotics, telemetry, dmn, bpmn, audit-ledger |
| 1223 | Research and Development Managers | Independent Research & Development Management Practice (**:implemented** — real `langgraph.graph` Actor: `rd-management.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 5312 | Teachers' Aides | Independent Teacher's Aide Practice (**:implemented** — real `langgraph.graph` Actor: `teachers-aide.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, audit-ledger, bpmn |
| 6122 | Poultry Producers | Independent Poultry Operations | robotics, telemetry, optimization, dmn, bpmn, audit-ledger, forms |
| 2431 | Advertising and Marketing Professionals | Independent Advertising & Marketing Practice (**:implemented** — real `langgraph.graph` Actor: `advertising-marketing.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 4120 | Secretaries (general) | Independent Secretarial Practice (**:implemented** — real `langgraph.graph` Actor: `secretarial.actor`/`.advisor`/`.governor`/`.store`, 10 tests) | robotics, forms, identity, audit-ledger, bpmn |
| 6123 | Apiarists and Sericulturists | Independent Apiary Operations | robotics, telemetry, dmn, bpmn, audit-ledger, forms |
| 2641 | Authors and Related Writers | Independent Writing Practice (**:implemented** — real `langgraph.graph` Actor: `writing-practice.actor`/`.advisor`/`.governor`/`.store`; craft library `kotoba-lang/shousetsu` enforces the body-as-blob invariant) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 2651 | Visual Artists | Independent Visual Art & Manga Studio (**:implemented** — real `langgraph.graph` Actor: `visual-art-studio.actor`/`.advisor`/`.governor`/`.store`; craft libraries `kotoba-lang/kami-genko` + `kami-mangaka-*`) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 2652 | Musicians, Singers and Composers | Independent Music Practice (**:implemented** — real `langgraph.graph` Actor: `music-practice.actor`/`.advisor`/`.governor`/`.store`; craft library `kotoba-lang/ongaku`) | robotics, identity, forms, dmn, bpmn, audit-ledger |
| 2654 | Film, Stage and Related Directors and Producers | Independent Video Production Studio (**:implemented** — real `langgraph.graph` Actor: `video-production.actor`/`.advisor`/`.governor`/`.store`; craft library `kotoba-lang/douga`) | robotics, identity, forms, dmn, bpmn, audit-ledger |

7-9 representative unit groups per non-armed-forces ISCO-08 major group
(89/89 across major groups 1-9, up from the original 84/84 representative
sample as occupations are added alongside promotions; major group 0
"Armed Forces Occupations" is registry-only — a sole-proprietor OSS
business blueprint doesn't fit an armed-forces occupation, mirroring how
`kotoba-industry` also leaves some sections registry-only). 6112, 2221,
7126, 4321, 9312, 5322, 8332, 1321, 3253, 6210, 5223, 7231, 8121, 9111,
2512, 1120, 4110, 3213, 5153, 7411, 2262, 4222, 5311, 6130, 8160, 2166,
2641, 2651, 2652, 2654, 1219, 1223, 1330, 1341, 1349, 1412, 1439, 2144,
2320, 2411, 2422, 2431, 2621, 2634, 3122, 3123, 3141, 3255, 3339, 3512,
4120, 4131, 4132, 4211, 4224, 4229, 4322, 4413, 4415, 5120, 5162, 5164,
5169, 5230, 5249, 5312, 6111, 6114, 6121 and 1212 are `:maturity
:implemented` (real reference actors exist); the other 19 are `:maturity
:blueprint`. The remaining 347 ISCO-08 unit groups are registered at
`:maturity :spec` (registry-only stub, full ISCO-08 coverage) for future
promotion.

Note: per the "Future promotions will follow the langgraph.graph pattern
going forward" direction, 46 of the 70 `:implemented` entries — 6130,
8160, 2166, 2641, 2651, 2652, 2654, 1219, 1223, 1330, 1341, 1349, 1412, 1439, 2144, 2320, 2411, 2422, 2431, 2621, 2634, 3122, 3123, 3141, 3255, 3339, 3512, 4120, 4131, 4132, 4211, 4224, 4229, 4322, 4413, 4415, 5120, 5162, 5164, 5169, 5230, 5249, 5312, 6111, 6114 and 6121 — are on the full itonami Actor
pattern (a real `langgraph.graph/state-graph` with Advisor/Governor as
distinct nodes and human-in-the-loop interrupt/resume, per AGENTS.md's
Actors section); the remaining 24 (including 1212) use the lighter
standalone `Store` + pure `governor/assess` function pattern from before
that direction was adopted.
