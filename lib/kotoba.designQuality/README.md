# kotoba-lang/design-quality

Deterministic HIG/WCAG UI-quality audit (pure `.cljc`) + CLI — the
*measurable* arm of the kotoba-lang design-quality system (ADR-2607132300).

Founding rule (carried from network-isekai's UX Co-Scientist, ADR-0007):
**an unmeasured metric is theater.** The subjective LLM-judge layer catches
what a regex can't (naming quality, rationale); this library is the
complementary deterministic arm — it scores ACTUAL rendered page source
(HTML + inline CSS) against Apple-HIG / WCAG / mobile-first heuristics with
no LLM and no browser. Each axis yields a 0..1 score, a weight, and a
concrete *finding* when it falls short. Re-running before/after an edit
yields the honest kaizen delta.

This repo is the single source of truth extracted from two prior forks
(`isekai.ux.audit` in gftdcojp/network-isekai and `design-quality.audit` in
the superproject's `90-docs/design-quality/`); both delegate here. See
[docs/design.md](docs/design.md) for the axis reconciliation.

## Axes

Core (`default-axes`, shared by both forks):

| axis | weight | heuristic |
|---|---|---|
| `:viewport` | 0.10 | `<meta name=viewport>` with device-width + initial-scale + viewport-fit=cover |
| `:safe-area` | 0.13 | ≥2 `env(safe-area-inset-*)` edges (notch / home indicator) |
| `:dynamic-viewport` | 0.09 | `100dvh`, not bare `100vh` |
| `:tap-targets` | 0.13 | interactive controls with `min-height ≥ 44px` (HIG) |
| `:focus-visible` | 0.09 | `:focus-visible` styles (WCAG 2.4.7) |
| `:reduced-motion` | 0.11 | motion guarded by `prefers-reduced-motion` (WCAG 2.3.3) |
| `:overflow-guard` | 0.06 | `overflow-x` guard against sideways scroll |
| `:color-scheme` | 0.06 | `<meta theme-color>` + `color-scheme`/`prefers-color-scheme` |
| `:responsive` | 0.07 | at least one `max-width` media query |
| `:semantics` | 0.05 | `<html lang>` + `<meta charset>` |

Optional (`extra-axes`, the isekai-origin additions):

| axis | weight | heuristic |
|---|---|---|
| `:input-zoom` | 0.09 | text fields ≥ 16px font (no iOS zoom-on-focus) |
| `:contrast` | 0.10 | muted text ≥ 4.5:1 over the page bg (WCAG 1.4.3) |

Scores are weight-normalized (`100 × Σ(score·w) / Σw`), so the weight sums
don't need to be 1.0.

## Library usage

```clojure
(require '[design-quality.audit :as audit])

(audit/score-page (slurp "index.html"))
;; => {:overall 71.55 :axes [{:id :viewport :score 0.66 :finding "..."} ...]}

(audit/audit {"home" src-a "settings" src-b})
;; => {:overall .. :pages {..} :findings [{:axis .. :headroom .. :finding ..} ...]}
;;    findings sorted heaviest-headroom first — the kaizen hypothesis seed list

;; consumers express deltas as data:
(audit/audit pages {:extra-axes audit/extra-axes    ;; full isekai 12-axis rubric
                    :weights    {:tap-targets 0.2}  ;; per-axis weight override
                    :skip       #{:contrast}        ;; drop axes by id
                    :axes       custom-axes})       ;; or replace the base set
```

## CLI (nbb / babashka; JVM optional)

```bash
kbb -M:score page.html dist/            # bb.edn task
bb  -m design-quality.cli score dist/
kbb --backend sci -m design-quality.cli score dist/

# options
... score dist/ --skip contrast,semantics \
                --weights weights.edn \
                --edn                     # EDN instead of the human report
... score dist/ --min 90                  # CI gate: exit 1 if aggregate < 90
```

`bb` and `nbb` produce byte-identical reports (deterministic number
formatting, no `format`).

## Known limits

Heuristics are static regex over source. Client-side-rendered apps whose
controls only exist at JS runtime can score false-positive on
`:tap-targets` / `:focus-visible` / `:input-zoom` (documented in
ADR-2607132300 addendum 3) — audit the built/rendered page, and concatenate
`<link>`-ed stylesheets into the source string before scoring.

## Dev

```bash
kbb -M:test    # cognitect test-runner
kbb -M:lint    # clj-kondo, --fail-level error
```

## Maturity

| | |
|---|---|
| Role | design-quality fitness function (deterministic arm) |
| Tests | `kbb -M:test` (12 tests, 161 assertions) + CI bb/nbb CLI smoke |
| Runtimes | nbb, babashka, ClojureScript, JVM |
| Third-party runtime deps | none (clojure.string only) |

## License

MIT
