# kotoba-lang/crm

Portable `.cljc` technical commons for CRM/subscription-commerce style
`cloud-itonami-*` actors — the reusable pieces that don't belong to any
one vertical:

- `kotoba.crm.pipeline` — generic ordered-stage transition validator for
  any funnel/pipeline domain (sales opportunity stages, marketing
  lifecycle stages, support-ticket lifecycle). No skipping ahead; exit
  stages (e.g. `:closed-lost`) reachable from any non-terminal stage;
  nothing transitions further once terminal.
- `kotoba.crm.revrec` — straight-line subscription revenue-recognition
  recompute (FASB ASC 606 / IASB IFRS 15), a pure ground-truth recompute
  in the same family `cloud-itonami-isic-6492`/`cloud-itonami-isic-6920`
  established elsewhere in this fleet.
- `kotoba.crm.leadscore` — deterministic weighted-point marketing
  lead-scoring recompute, the same pure ground-truth-recompute family as
  `revrec` applied to lead score instead of recognized revenue. Unlike
  `revrec` there is no external standard-setter to cite for the point
  weights, so the point table is this namespace's own documented spec.
- `kotoba.crm.funnel` — aggregate cross-record pipeline funnel/conversion
  analytics for dashboards (point-in-time snapshot distribution,
  cumulative "how far did entities get" counts, and stage-to-stage
  conversion rates). This is a DISTINCT concept from each actor's own
  `crm.report`/`report.cljc` (governed single-record disclosure
  rendering) — `funnel` never renders or discloses a single record, it
  only aggregates counts across many. Relies on
  `kotoba.crm.pipeline/valid-transition?`'s forward-only, no-skip
  invariant, and is explicit about the one real ambiguity it does not
  guess through: which forward stage an exited entity (e.g.
  `:closed-lost`) came from.

First consumers: [`cloud-itonami-isic-5820`](https://github.com/cloud-itonami/cloud-itonami-isic-5820)
(commercial CRM/subscription-commerce SaaS platform business, the
Salesforce/HubSpot-class vertical) uses `pipeline` and `revrec`;
`cloud-itonami-isic-6201` (marketing-automation SaaS platform business,
the HubSpot Marketing Hub/Salesforce Marketing Cloud-class vertical)
uses `pipeline` and `leadscore`. `funnel` is designed for reuse by any
sibling actor that wants a dashboard-style funnel rollup on top of its
own `pipeline`-shaped stages. Designed to be reused by further sibling
actors without re-deriving stage-graph, revenue-recognition,
lead-scoring, or funnel-analytics logic per actor.

## Scope (deliberately narrow)

- `pipeline`: linear stage graphs with a single ordered path plus flat
  exit stages. Branching/parallel or re-enterable stage graphs are out of
  scope.
- `revrec`: single-performance-obligation, fixed-fee, straight-line term
  subscriptions only. Usage-based billing, contract modifications, and
  multi-element arrangement allocation (ASC 606 step 4) are NOT modeled.
- `leadscore`: a fixed weighted-point sum over a documented event-kind
  table only. No ML/predictive scoring, no per-account custom weight
  overrides, and no decay of a lead's score for inactivity are modeled;
  per-event recency time-decay is supported but opt-in and off by
  default.
- `funnel`: a single point-in-time snapshot only (no stage-history log,
  no time dimension, no cohort-over-time trending). Entities currently
  in an exit stage are excluded from `reached-counts`/`conversion-rate`
  by default — which forward stage they exited from is not guessed —
  unless the caller supplies an explicit `:reached-stage` fact. Not
  modeled at all: time-in-stage/velocity metrics, multi-touch
  attribution, and exit-stage sub-classification (e.g. won vs lost)
  beyond whatever exit-stage keywords the caller's own pipeline encodes.

## Operator quickstart

[`docs/operator-quickstart.md`](docs/operator-quickstart.md) walks all four
namespaces end to end with real, executed outputs, and covers the four places
these functions return `nil` ("no opinion") instead of guessing — which is what
a consuming governor most often gets wrong.

## Test

Two hosts, because every namespace here is `.cljc` and three of them carry a
reader conditional (`revrec/round-cents`, `leadscore/decay-multiplier`,
`leadscore/round-points`). A `:cljs` branch is structurally invisible from the
JVM, so a suite with one host cannot tell a portable library from one that
only happens to work where it is run.

```bash
kbb -M:test                                    # JVM       — 32 tests, 165 assertions
kbb --backend sci --classpath "src:test" test/run_portable.cljk  # nbb/cljs  — 32 tests, 165 assertions
kbb -M:lint                                    # errors: 0, warnings: 0
```

The portable runner exits `2` (`REFUSED`), not `0`, when it cannot vouch for
what it covered — a run that quietly covers less than `test/` contains
otherwise prints the same "0 failures" as a run that really passed. What it
buys is measured, in both directions: dropping cent-rounding on the `:cljs`
side only leaves `kbb -M:test` green and turns the nbb run red; dropping
it on the `:clj` side does the reverse. Neither host alone discriminates.

These invariants are held to the standard the workspace applies to gates —
each one was checked by breaking the implementation and watching the named
test go red. The mutations are registered in the superproject's
`scripts/maturity-loop/mutations.edn` so the check does not decay silently:

```bash
kbb --backend sci scripts/maturity-loop/run.cljk --only crm      # run from the superproject
```
