# kotoba-industry

Industry registry for kotoba-lang and itonami open businesses.

This repository maps ISIC-coded businesses to the technology capabilities they
need in order to operate. `cloud-itonami-*` uses this to move from a published
business model to an executable operating stack.

## Contract

```clojure
(require '[kotoba.industry :as industry])

(industry/get-industry "3512")
(industry/required-technologies "3600")
(industry/readiness "8691" #{:forms :identity :audit-ledger :bpmn :dmn})
```

## Layers

- business: customer-facing open business model
- industry: ISIC-coded operating domain
- technology: reusable kotoba-lang capability stack
- implementation: concrete repos, services and operators

## Current ISIC Blueprints

<!-- BEGIN GENERATED ISIC BLUEPRINTS (kbb --backend sci scripts/gen-industry-docs.cljk) -->

A curated highlight set (community/open-business reference blueprints, plus every implemented engineering/heavy-industry/mining ISIC entry). This block is generated from `resources/kotoba/industry/registry.edn` -- do not hand-edit it, run `kbb --backend sci scripts/gen-industry-docs.cljk` instead. The full list of all 347 `:implemented` entries lives in [`docs/isic-coverage.md`](docs/isic-coverage.md).

### Community / open-business reference blueprints

| ISIC | Business | business-id |
|---|---|---|
| 3512 | Community Renewable Energy Operations | cloud-itonami-isic-3512 |
| 3600 | Community Water Safety Operations | cloud-itonami-isic-3600 |
| 3830 | Local Materials Recovery | cloud-itonami-isic-3830 |
| 6310 | Talent Actor | cloud-itonami-isic-6310 |
| 8569 | Community Learning Support | cloud-itonami-isic-8569 |
| 8691 | Health Access Navigation | cloud-itonami-isic-8691 |
| 8810 | Community Care Coordination | cloud-itonami-isic-8810 |

### Engineering, heavy-industry and mining blueprints

See [`docs/engineering.md`](docs/engineering.md) for the technology-stack framing; full list of the 69 implemented codes:

| ISIC | Business | business-id |
|---|---|---|
| 0510 | Mining of hard coal | cloud-itonami-isic-0510 |
| 0520 | Mining of lignite | cloud-itonami-isic-0520 |
| 0610 | Extraction of crude petroleum | cloud-itonami-isic-0610 |
| 0620 | Extraction of natural gas | cloud-itonami-isic-0620 |
| 0710 | Mining of iron ores | cloud-itonami-0710 |
| 0721 | Mining of uranium and thorium ores | cloud-itonami-isic-0721 |
| 0729 | Mining of other non-ferrous metal ores | cloud-itonami-0729 |
| 0810 | Community Quarry and Stone Supply | cloud-itonami-0810 |
| 0891 | Mining of chemical and fertilizer minerals | cloud-itonami-isic-0891 |
| 0892 | Extraction of peat | cloud-itonami-isic-0892 |
| 0893 | Extraction of salt | cloud-itonami-isic-0893 |
| 0910 | Support activities for petroleum and natural gas extraction | cloud-itonami-isic-0910 |
| 0990 | Support activities for other mining and quarrying | cloud-itonami-isic-0990 |
| 2410 | Manufacture of Basic Iron and Steel | cloud-itonami-isic-2410 |
| 2420 | Manufacture of basic precious and other non-ferrous metals | cloud-itonami-isic-2420 |
| 2431 | Casting of iron and steel | cloud-itonami-isic-2431 |
| 2432 | Casting of non-ferrous metals | cloud-itonami-isic-2432 |
| 2511 | Manufacture of structural metal products | cloud-itonami-isic-2511 |
| 2512 | Manufacture of tanks, reservoirs and containers of metal | cloud-itonami-isic-2512 |
| 2591 | Forging, pressing, stamping and roll-forming of metal | cloud-itonami-isic-2591 |
| 2592 | Treatment and coating of metals | cloud-itonami-isic-2592 |
| 2593 | Manufacture of cutlery, hand tools and general hardware | cloud-itonami-isic-2593 |
| 2599 | Manufacture of other fabricated metal products n.e.c. | cloud-itonami-isic-2599 |
| 2610 | Semiconductor and Electronics Manufacturing Enablement | cloud-itonami-isic-2610 |
| 2620 | Manufacture of computers and peripheral equipment | cloud-itonami-isic-2620 |
| 2630 | Manufacture of communication equipment | cloud-itonami-isic-2630 |
| 2640 | Manufacture of consumer electronics | cloud-itonami-isic-2640 |
| 2651 | Manufacture of measuring, testing, navigating and control e... | cloud-itonami-isic-2651 |
| 2652 | Manufacture of watches and clocks | cloud-itonami-2652 |
| 2660 | Manufacture of irradiation, electromedical and electrothera... | cloud-itonami-2660 |
| 2670 | Manufacture of optical instruments and photographic equipment | cloud-itonami-isic-2670 |
| 2680 | Manufacture of magnetic and optical media | cloud-itonami-isic-2680 |
| 2710 | Manufacture of electric motors, generators, transformers an... | cloud-itonami-isic-2710 |
| 2720 | Manufacture of batteries and accumulators | cloud-itonami-isic-2720 |
| 2731 | Manufacture of fibre optic cables | cloud-itonami-isic-2731 |
| 2732 | Manufacture of other electronic and electric wires and cables | cloud-itonami-isic-2732 |
| 2733 | Manufacture of wiring devices | cloud-itonami-isic-2733 |
| 2740 | Manufacture of electric lighting equipment | cloud-itonami-isic-2740 |
| 2750 | Manufacture of domestic appliances | cloud-itonami-isic-2750 |
| 2790 | Manufacture of other electrical equipment | cloud-itonami-isic-2790 |
| 2811 | Manufacture of Engines and Turbines | cloud-itonami-isic-2811 |
| 2812 | Manufacture of fluid power equipment | cloud-itonami-isic-2812 |
| 2813 | Manufacture of other pumps, compressors, taps and valves | cloud-itonami-isic-2813 |
| 2814 | Manufacture of bearings, gears, gearing and driving elements | cloud-itonami-isic-2814 |
| 2816 | Manufacture of lifting and handling equipment | cloud-itonami-isic-2816 |
| 2817 | Manufacture of office machinery and equipment (except computers and peripheral equipment) | cloud-itonami-isic-2817 |
| 2818 | Manufacture of power-driven hand tools | cloud-itonami-isic-2818 |
| 2819 | Manufacture of other general-purpose machinery | cloud-itonami-isic-2819 |
| 2821 | Manufacture of agricultural and forestry machinery | cloud-itonami-isic-2821 |
| 2822 | Manufacture of metal-forming machinery and machine tools | cloud-itonami-isic-2822 |
| 2824 | Manufacture of machinery for mining, quarrying and construction | cloud-itonami-isic-2824 |
| 2825 | Manufacture of machinery for food, beverage and tobacco pro... | cloud-itonami-isic-2825 |
| 2826 | Manufacture of machinery for textile, apparel and leather p... | cloud-itonami-isic-2826 |
| 2910 | Manufacture of motor vehicles | cloud-itonami-isic-2910 |
| 2920 | Manufacture of bodies (coachwork) for motor vehicles | cloud-itonami-isic-2920 |
| 2930 | Manufacture of parts and accessories for motor vehicles | cloud-itonami-isic-2930 |
| 3011 | Building of Ships and Floating Structures | cloud-itonami-isic-3011 |
| 3012 | Building of pleasure and sporting boats | cloud-itonami-isic-3012 |
| 3020 | Manufacture of railway locomotives and rolling stock | cloud-itonami-3020 |
| 3030 | Aircraft and Aerospace Manufacturing Enablement | cloud-itonami-isic-3030 |
| 3091 | Manufacture of motorcycles | cloud-itonami-isic-3091 |
| 3092 | Manufacture of bicycles and invalid carriages | cloud-itonami-isic-3092 |
| 3099 | Manufacture of other transport equipment n.e.c. | cloud-itonami-isic-3099 |
| 3311 | Repair of fabricated metal products | cloud-itonami-isic-3311 |
| 3312 | Repair of machinery | cloud-itonami-3312 |
| 3313 | Repair of electronic and optical equipment | cloud-itonami-3313 |
| 3314 | Repair of electrical equipment | cloud-itonami-isic-3314 |
| 3319 | Repair of other equipment | cloud-itonami-isic-3319 |
| 3320 | Installation of industrial machinery and equipment | cloud-itonami-isic-3320 |

<!-- END GENERATED ISIC BLUEPRINTS -->

Engineering/manufacturing ISICs can add EDA/CFD/CAE through the same registry.

## Legacy ISIC group codes and supersession

The registry was originally seeded with a broad ISIC skeleton at 3-digit
**group** granularity (e.g. `"241"`), then filled in with the proper 4-digit
ISIC Rev.4 **class** granularity one real actor at a time (e.g. `"2410"`).
Where a legacy group entry has a real, more specific `:implemented`
successor, it is marked `:superseded-by ["2410"]` (or, for the small number
of legacy group ids that were themselves directly implemented,
`:superseded-code`) rather than silently deleted -- see
`docs/isic-coverage.md` for the full generated breakdown of superseded vs.
genuinely-unimplemented legacy entries.

## Portable, and how the registry gets compiled in

`kotoba.industry` is `.cljc` and touches **no file at runtime** (so is
`kotoba.industry.wave`, which always was). The registry lives in
`resources/kotoba/industry/registry.edn` — that is still the source of truth
and the only thing to edit — and `tools/gen-embedded.cljk` projects it into
the generated `src/kotoba/industry/embedded.cljk`, which is what the library
reads.

`io/resource` has no portable equivalent, and reading `resources/<path>`
relative to the working directory is right only while this library is the
root project — measured wrong on 2026-08-18, when `kotoba-lang/technology`
briefly worked that way and returned nil for all 159 of `kotoba.iso3166`'s
assertions under nbb. This registry has more consumers ahead of it than any
other in the workspace, so it is compiled in instead.

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
