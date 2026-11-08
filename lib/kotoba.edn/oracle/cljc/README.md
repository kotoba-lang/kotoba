# oracle/cljc — kotoba.lang.edn measurement twin (JUN-1023)

One-off measurement oracle for `kotoba.lang.edn`. Never a CI gate,
build, runtime or fallback input (ADR 0026 D18). Divergences found here
are reported, never silently aligned.

## Layout

- `src/kotoba/lang/edn.cljc` — portable EDN reader (ns `kotoba.lang.edn`),
  mechanically extracted from the `.cljk` host `:default` branch with
  every interop point given a `:lpy` branch (`char-code`, `code-str`,
  `parse-long-twin`, `parse-double-twin`, `parse-long-base`,
  `to-hex-str`, `utf8-byte-count`; atom instead of `volatile!`, vector
  instead of transient, cause dropped from the rethrow because Basilisp
  cannot inline 3-argument `ex-info`).
- `test/edn_oracle_cases.cljc` — 67 shared cases + 3 must-fail cases.
- `test/run.cljc` — runner (same output contract as the json twin).
- `run.sh` — runs bb, nbb and Basilisp and `cmp`s the outputs.

## Why this placement (verified 2026-11-08)

Same nbb-shadowing result as the json twin: a twin next to `edn.cljk`
never loads on nbb. Twins live here, where no `.cljk` exists, and
`run.sh` puts this `src/` first on the classpath. (`kotoba.*` has no
Python stdlib collision, so the real `kotoba.lang.edn` name is kept.)

Basilisp constraints discovered while porting (all pinned by cases):

- no `array-map` (use `into {}` — keeps insertion order when printed on
  every runner); `sorted-map` untested, avoid it.
- `volatile!` and 3-argument `ex-info` do not compile; atom and 2-argument
  `ex-info` are used instead.
- a real `\u` escape followed by 5+ hex chars is a reader error, so cases
  keep a non-hex char after every real `\u` escape; data files are `.cljc`
  (host readers), never EDN.

## Verification record (2026-11-08)

- `run.sh`: 70/70 on babashka 1.12.218, nbb on node v26.0.0, basilisp
  0.5.1 / python 3.14.7. Full outputs byte-identical (`cmp` clean).
- must-fail: 3 deliberately wrong cases, each confirmed FAIL-inverted.
- mutation control: relaxing `max-depth` to 100000 makes exactly
  `:neg/depth-limit` FAIL; revert restores 70/70.
- known divergences from the host (in the twin docstring): character
  literals read to one-character strings (matches the host's own `:cljs`
  reading; host `:clj` answers Characters); lone `\uD800`-`\uDFFF` kept
  as lone-surrogate strings like the host; `write-string` of C0-control
  strings prints `\xNN` on Basilisp but `\uNNNN` on bb/nbb (printer, not
  reader — cases pin controls through `escape-controls` directly).
