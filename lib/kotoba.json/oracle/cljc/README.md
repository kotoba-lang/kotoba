# oracle/cljc — kotoba.json measurement twin (JUN-1024)

One-off measurement oracle for `kotoba.lang.json`. Never a CI gate,
build, runtime or fallback input (ADR 0026 D18). Divergences found here
are reported, never silently aligned.

## Layout

- `src/kotoba/json/twin.cljc` — portable JSON engine (ns `kotoba.json.twin`),
  ported from json.core's `.cljk` host branches (`:clj` taken as base;
  `:cljs` is identical except parse interop).
- `src/kotoba/lang/json.cljc` — facade twin (ns `kotoba.lang.json`),
  delegates to the twin engine. No `{:kotoba/export}` metadata (Basilisp
  rejects unknown ns metadata).
- `test/json_oracle_cases.cljc` — 47 shared cases + 3 must-fail cases.
- `test/run.cljc` — runner (one line per case + fixed-order summary;
  values print only on failure so green output is byte-identical).
- `run.sh` — runs bb, nbb and Basilisp and `cmp`s the outputs.

## Why this placement and these names (verified 2026-11-08)

- nbb prefers a sibling `.cljk` over `.cljc`: a twin next to the source
  never loads on nbb (the `.cljk` shadows it, and the oracle then measures
  the host instead of the twin). Twins live here, where no `.cljk` exists,
  and `run.sh` puts this `src/` first on the classpath.
- Basilisp cannot load any `json.*` namespace: top-level `json` resolves to
  Python's stdlib `json` and `json.core` is then looked up inside it. The
  engine is therefore `kotoba.json.twin`. Same reason the twin never
  requires the `.cljk` `json.core`.
- Basilisp's language reader greedily reads `\uNNNN` + hex: a real `\u`
  escape followed by 5+ hex chars (`"\u0001b"`) is a reader error, so
  shared cases keep a non-hex char after every real `\u` escape. Data files
  are `.cljc` (host readers), never EDN: basilisp.edn rejects even `\\u`.

## Verification record (2026-11-08)

- `run.sh`: 50/50 on babashka 1.12.218, nbb on node v26.0.0, basilisp
  0.5.1 / python 3.14.7. Full outputs byte-identical (`cmp` clean).
- must-fail: 3 deliberately wrong cases, each confirmed FAIL-inverted
  (a broken harness would show them red).
- mutation control: removing the trailing-comma refusals makes exactly
  `:neg/trailing-array-comma`, `:neg/trailing-object-comma` (plus the
  inverted `:must-fail/refused-passes`) FAIL; revert restores 50/50.
- known divergences from the host (in the twin docstring): lone
  `\uD800`-`\uDFFF` refused (host keeps); whole floats past Long range
  print host-dependently (cases stay inside Long range).
