# CSSOM Q6 slice 2: calc, line-height / metrics, aspect-ratio / replaced sizing (JUN-920 / C2b)

Date: 2026-11-06. Branch `claude/jun-920-q6-slice-2`, built on the head of #1255 (slice 1, open). Source, tests, gate and the
narrative are in `lib/kotoba.cssom` (README section "Q6 fixed-point slice 2"). This directory holds the data.

* `oracle-attempt.txt` - the one-time attempt to run the original `.cljk` (kbb / nbb): it failed to load; command, tool versions,
  output. No value from the original code is used anywhere.
* `hand-derived-cases.tsv` - 33 cases taken from `core_test.cljk` assertions and `layout.cljk` comments (Brave measurements),
  with file and line, and the native test that checks each.
* `measurements.json` - the measured table the gate pins (`scripts/check-calc-q6-native-macos.py --print-measurements`):
  per-shape calc counts and maximum deviation, the dense tie sweeps, the line-height and aspect-ratio counters, kernel-v1 text
  bytes and user-v1 error codes.
* Gate: `python3 lib/kotoba.cssom/scripts/check-calc-q6-native-macos.py --amu amu-cli.macho --amu-full-root amu-full-root.macho
  --output <new dir>` printed `PASS_NATIVE_CSSOM_CALC_LINE_ASPECT_Q6` (about 60 s on macOS arm64, pinned `amu-cli.macho` sha256
  `e13a2054...2b02`, `amu-full-root.macho` sha256 `88623412...a229`).
