# oracle/cljc — kotoba.text measurement twin (JUN-1044)

One-off measurement oracle for `kotoba.lang.text`. Never a CI gate,
build, runtime or fallback input (ADR 0026 D18). Divergences found here
are reported, never silently aligned.

## Layout

- `src/kotoba/lang/text.cljc` — curated twin (ns `kotoba.lang.text`),
  copied from `lib/kotoba.text/src/kotoba/lang/text.cljc`. Curated:
  excluded from `scripts/oracle-cljc-mirror.sh` rewrites (CURATED list),
  because the mirror product is a byte-copy carrying `{:kotoba/export}`
  which Basilisp rejects, and node resolution differs.
- `test/text_oracle_cases.cljc` — 62 shared cases + 3 must-fail cases
  (65 total), data as `.cljc` code (never EDN: readers differ on `\u`).
- `test/run.cljc` — runner (one line per case + fixed-order summary;
  values print only on failure so green output is byte-identical).
- `run.sh` — runs bb, nbb and Basilisp and `cmp`s the outputs.

## Why this placement (verified 2026-11-08)

- nbb prefers a sibling `.cljk` over `.cljc`: a twin next to the source
  never loads on nbb (the `.cljk` shadows it, and the oracle then
  measures the host instead of the twin). The twin lives here, where no
  `.cljk` exists, and `run.sh` puts this `src/` first on the classpath.
  Verified via `(:file (meta #'kotoba.lang.text/trim))`.
- `{:kotoba/export}` ns metadata is dropped: Basilisp rejects unknown ns
  metadata. The twin also never requires the `.cljk` source.
- Basilisp's language reader greedily reads `\uNNNN` + hex digit: a real
  `\u` escape immediately followed by a hex char (`\u00a0a`) fails to
  read. Cases keep non-hex neighbours around `\u` escapes (`g\u00a0h`).
- `re-find` with groups returns a vector on all three runners; the
  no-group shape returns a bare string (Clojure-compatible; the twin
  never returned `[m]`).
- `trim-newline` strips only trailing newlines (Clojure-compatible);
  leading newlines are kept.
- `trim` removes ASCII controls incl. `\u001c`/`\u001f` but keeps NBSP
  (`\u00a0`) and figure space (`\u2007`); em space (`\u2003`) trims.

## Results (2026-11-08)

- `sh run.sh` → 65/65 on babashka 1.12.218, nbb on node v26.0.0,
  basilisp 0.5.1, byte-identical (`cmp`) across all three.
- Mutation control: flipping `:join/basic` expect fails on all three
  runners (`fail: [:join/basic]`), restore returns 65/65.
