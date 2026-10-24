# hinshitsu

[![CI](https://github.com/kotoba-lang/hinshitsu/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/hinshitsu/actions/workflows/ci.yml)

`hinshitsu`（品質 — quality）is the Kotoba shared **software-quality toolkit**:
a portable evidence/gate schema plus a visual/snapshot testing module
(`hinshitsu.mokushi`, 黙視 — "to watch in silence"). Pure `.cljc` (JVM /
ClojureScript / SCI / babashka); actual process work (screenshot capture,
image diffing) is delegated to system binaries, not linked in as libraries.

```text
hinshitsu = evidence schema + gate aggregation + coverage assessment
mokushi   = capture + pixel-diff-vs-baseline + evidence, on top of hinshitsu
```

## Why

`kotoba-shell` (and other kotoba tools) each hand-roll their own
`SdkCheckStatus` / `*CheckReport` / `EvidenceCheckReport` shapes — every
check reinvents "passed/skipped/failed + checks + detail". `hinshitsu.core`
generalizes that into one reusable EDN schema (`hinshitsu.evidence.v0`) any
kotoba tool can produce and consume, and `hinshitsu.mokushi` adds the one
check kind none of them have yet: does the rendered UI actually look right,
not just "did it launch."

## Layers

| ns | role |
|---|---|
| `hinshitsu.core` | `evidence` / `passed?` / `failed?` / `skipped?` constructors and predicates; `gate` (aggregate many evidence maps into one pass/fail decision, optionally requiring specific check names); `coverage` (implemented/partial/missing maturity assessment) |
| `hinshitsu.mokushi` | `capture!` (run a caller-supplied screenshot command), `compare!` (ImageMagick `compare -metric RMSE` against a committed baseline, threshold-gated), `check!` (capture + compare in one call), `save-baseline!` (deliberate baseline promotion) |

## iOS simulator visual QA CLI

`bin/hinshitsu-ios-visual-qa` is the shared executable contract for native iOS
simulator visual checks. It requires a successful app launch before capture,
rejects black screens, compares RMSE against a baseline, applies hard timeouts,
and emits a `hinshitsu.ios-visual.v0` JSON receipt.

```bash
bin/hinshitsu-ios-visual-qa \
  --bundle-id jp.co.example.app \
  --baseline test/visual/ios.png \
  --candidate target/visual/ios-current.png
```

App repositories should keep only a thin wrapper supplying their bundle ID and
paths. The shared CLI never installs, signs, submits, or changes a baseline.

## Contract

```clojure
(require '[hinshitsu.core :as h]
         '[hinshitsu.mokushi :as m])

(h/evidence :passed ["built" "launched"] "manimani launched on iOS simulator")
;; => {:hinshitsu/schema "hinshitsu.evidence.v0" :hinshitsu/status :passed ...}

(h/gate [build-evidence launch-evidence])
;; => single pass/fail evidence; fails if ANY input is :failed

(m/compare! "baselines/manimani-home.png" "captures/manimani-home.png")
;; => {:hinshitsu/status :passed, :data {:distortion 0.0 :threshold 0.02 ...}}
;; :skipped (not :failed) if no baseline exists yet -- see save-baseline!
```

No baseline yet? `compare!` returns `:skipped`, not `:failed` — mokushi never
invents a false failure for a check that was never recorded, and never
overwrites a baseline on its own (`save-baseline!` is a deliberate, separate
call).

## Verify

```bash
kbb -M:test
```

`hinshitsu.mokushi`'s `capture!`/`compare!`/`save-baseline!` are `:clj`/`:bb`
only (they shell out to ImageMagick's `compare`/`convert`); on `:cljs`,
`compare!` returns `:skipped` evidence explaining why.

## License

Apache License 2.0.
