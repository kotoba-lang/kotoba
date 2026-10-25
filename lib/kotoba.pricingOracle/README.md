# pricing-oracle

Market-analogy price prediction for verticals where real research found no self-serve price at
all — quote-only, sales-gated, "contact for pricing" markets. Given a set of verticals where some
have a real, independently-researched price band and some don't, predicts the missing bands from
the ones that *are* priced — never from a prior, always from comparables actually present in the
input data.

Built for [`com-junkawasaki/root`](https://github.com/com-junkawasaki/root)'s
`90-docs/pricing-intelligence/` dataset (`cloud-itonami` vertical-module pricing research — see
that repo's `90-docs/pricing-intelligence/README.md`), but the core (`pricing-oracle.core`) is
domain-agnostic: it knows nothing about ISIC/ISCO, clusters, or currencies, only a generic item
shape (see below).

## Why a separate repo, and why predictions never touch the source ledger

`pricing-intelligence-ledger.edn`'s entire value is that every number in it is either real vendor
pricing, an explicitly labeled third-party estimate, or explicitly marked opaque — nothing is
ever synthesized. A median-of-comparables prediction is a different epistemic kind of thing
entirely (a model's output, not an observation), so it gets its own namespace (`:pred/*`), its own
output file (`predictions.edn`), and is never written back into that ledger. `bin/predict.cljk`
only *reads* the source dataset.

## Method (stated plainly — this is not an ML model)

`pricing-oracle.core/predict-band` is a same-cluster / same-unit median-of-real-comparables
estimator. For a gap item it looks for comparables in this order, most specific first:

1. same `:cluster` **and** same `:unit` — tightest, most defensible
2. same `:cluster`, any `:unit` — the dominant real-world path, since free-text unit/rationale
   strings rarely match verbatim across verticals even within the same market, while the industry
   cluster is a strong real signal for "comparable price scale"
3. same `:unit`, any cluster — a verbatim unit-string match in an unrelated industry
4. same coarse shape-family (`per-seat` / `per-unit-managed` / `per-transaction` /
   `enterprise-contract` / other) — cross-industry, last resort, always low confidence; can blend
   genuinely different price scales (e.g. monthly per-seat SaaS with annual enterprise contracts)

`:confidence` (`:high` / `:medium` / `:low` / `:none`) is a coarse label for how many real
comparables backed the prediction and how directly comparable they are — not a calibrated
probability. Every prediction carries `:basis-vertical-ids` (or `:basis-ids` in the core's generic
shape) so a human can always check the actual real data a number rests on, and can discount or
reject predictions whose basis looks like a bad analogy.

## Layout

```
src/pricing_oracle/core.cljk   pure prediction logic — median, known?, shape-family, predict-band,
                                predict-all-gaps. No I/O, no host interop. Runs under kotoba wasm /
                                clojurewasm / ClojureScript / nbb / JVM equally (ADR-0016 order).
bin/predict.cljk               cloud-itonami-specific adapter: loads pricing-intelligence's EDN,
                                joins :vertical/* + latest :rec/* into core's generic item shape,
                                runs predict-all-gaps, writes predictions.edn.
test/pricing_oracle/core_test.cljk   nbb test (self-contained script + manual check, this
                                       workspace's nbb convention — not cljs.test).
```

## Generic item shape (what `pricing-oracle.core` actually operates over)

```clojure
{:id "isic-8610" :cluster :cluster/healthcare :unit "$/seat/mo"
 :band-low 10.0 :band-high 20.0}   ; band-low/band-high nil == a gap to predict
```

## Usage

```sh
kbb --backend sci --classpath src test/pricing_oracle/core_test.cljk   # unit tests

kbb --backend sci --classpath src bin/predict.cljk /path/to/com-junkawasaki predictions.edn
```

Sample real run against `com-junkawasaki/root`'s pricing-intelligence dataset (211 verticals, 2026-07-16):

```
loaded 211 verticals from pricing-intelligence
of which 137 have a real researched band (comparables)
and 74 are gaps (no self-serve band found in research)

wrote 74 predictions to predictions.edn

confidence breakdown:
  :medium 74
```

All 74 gaps resolved via `:cluster-fallback` (same industry cluster, real sibling bands) at
`:medium` confidence — see `predictions.edn` for the full output, each line carrying its
`:pred/basis-vertical-ids` back to the real research it was derived from.

## Non-goals

Not a trained model, not a calibrated probability, not a substitute for actually researching a
quote-only market when the stakes justify it. Treat every `:pred/*` value as a market estimate to
disclose as such — never present it as an observed or quoted price.
