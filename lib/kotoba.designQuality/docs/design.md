# design-quality — design notes

## Why this repo exists

The deterministic UI-quality audit lived as two divergent copies:

1. **`isekai.ux.audit`** (`orgs/gftdcojp/network-isekai/src/isekai/ux/audit.cljc`,
   isekai ADR-0007) — the origin. 12 axes, including `:input-zoom` and a WCAG
   1.4.3 `:contrast` axis with a small sRGB contrast calculator.
2. **`design-quality.audit`** (superproject `90-docs/design-quality/audit.cljc`,
   ADR-2607132300 addendum) — a 10-axis port with kotoba-ui-specific finding
   text; `:contrast` was explicitly deferred as a follow-up and `:input-zoom`
   was dropped.

Two copies means drift: a threshold fixed in one fork silently stays broken in
the other. This repo is the SSoT; both prior locations become thin wrappers
that delegate here and express their remaining differences **as data** through
the opts map.

## Axis reconciliation (what differed between the forks, and how the lib expresses it)

| difference | isekai (origin) | superproject port | in this lib |
|---|---|---|---|
| `:input-zoom` axis (w=0.09) | present | absent | `input-zoom-axis`, optional — splice via `{:extra-axes extra-axes}` |
| `:contrast` axis (w=0.10) | present (sRGB calculator, muted-text heuristic) | absent (listed as follow-up) | `contrast-axis`, optional — same splice; the color machinery (`parse-color`, `contrast-ratio`, `relative-luminance`) is public |
| `:tap-targets` control detection | `<button` / `.btn` / `role="button"` | `<button` / `liquid-glass__button` / `liquid-glass__icon-button` | union of both patterns in `default-axes` — each fork's pages keep detecting |
| finding text | generic | kotoba-ui/liquid-glass-specific prose (e.g. names `.kotoba-shell__app`) | generic text in core; a consumer that wants bespoke wording overrides the axis via `{:axes ...}` |
| everything else (10 axes, weights, thresholds, `score-page`/`audit` shapes, weight-normalized overall, headroom-sorted findings) | identical | identical | kept verbatim |

Consumer wrappers therefore reduce to:

```clojure
;; isekai.ux.audit
(defn score-page [src] (dq/score-page src {:extra-axes dq/extra-axes}))
(defn audit [pages]    (dq/audit pages    {:extra-axes dq/extra-axes}))

;; superproject design-quality.audit (core rubric as-is)
(defn score-page [src] (dq/score-page src))
(defn audit [pages]    (dq/audit pages))
```

The isekai `format` call in the contrast finding was rewritten to `str` +
a `round1` helper — `format` doesn't exist on nbb and float rendering differs
between hosts.

## Shape compatibility

`score-page` → `{:overall 0..100 :axes [{:id :title :weight :score :finding}]}`
and `audit` → `{:overall :pages :findings [{:axis :weight :pages :finding
:worst-score :headroom}]}` are exactly the shapes both forks already return,
so downstream tooling (the superproject's coscientist loop, isekai's kaizen
loop, the design-quality ledger writers) keeps working unchanged after the
wrappers delegate.

## Purity / runtime split

- `design-quality.audit` — pure: string in, data out. No IO, no reader
  conditionals except number parsing (`Long/parseLong` vs `js/parseInt`) and
  no `format`. Runs on nbb, bb, cljs, JVM.
- `design-quality.cli` — all IO lives here (node `fs` on cljs, `clojure.java.io`
  on JVM/bb), behind reader conditionals. Deterministic 2-decimal formatting
  (`fmt2`) keeps bb and nbb reports byte-identical. `run` returns
  `{:exit :result}` without exiting (testable); `-main` only calls
  `System/exit` / `process.exit` on non-zero, so bb task invocation stays clean.

Per the workspace runtime-priority rule, the first-class runtimes for the CLI
are **nbb and bb** (`nbb.edn`/`bb.edn` both carry `:paths ["src"]`); the JVM
path exists because the test suite runs there.

## Deliberate non-goals

- No browser, no LLM, no third-party deps — determinism is the point.
- No DOM parsing: regex-over-source is deliberately simple and conservative
  (a missing signal scores low and emits a finding). Known false-positive
  surface on CSR apps is documented in the README and the ns docstring.
- Fixtures here are two tiny synthetic pages (`test/fixtures/good.html`,
  `bad.html`); the superproject's four checked-in sample pages stay where
  they are.
