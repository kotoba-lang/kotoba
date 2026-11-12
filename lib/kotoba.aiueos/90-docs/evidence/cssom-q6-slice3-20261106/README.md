# CSSOM Q6 slice 3: flex, multi-column, style numbers, inline shifts, colour (JUN-920 / C2b)

Date: 2026-11-06. Branch `claude/jun-920-q6-slice-3`, built on the head of #1259 (slice 2, open). Source, tests, gate and the
narrative are in `lib/kotoba.cssom` (README section "Q6 fixed-point slice 3"). This directory holds the data.

* `hand-derived-cases.tsv` - the spec points the f64 references are validated against (derived by hand from the
  `resolve-flexible-lengths` docstring tables, the multicol comment, CSS Color 4 and the code comments), with the native test
  that checks each. The original `.cljk` was not run (see the slice-2 evidence `oracle-attempt.txt`).
* `measurements.json` - the measured table the gate pins (`scripts/check-flex-q6-native-macos.py --print-measurements`).
* Gate: `python3 lib/kotoba.cssom/scripts/check-flex-q6-native-macos.py --amu amu-cli.macho --amu-full-root amu-full-root.macho
  --output <new dir>` prints `PASS_NATIVE_CSSOM_FLEX_COLOUR_Q6` (about 85 s on macOS arm64, pinned `amu-cli.macho` sha256
  `e13a2054...2b02`, `amu-full-root.macho` sha256 `88623412...a229`).
