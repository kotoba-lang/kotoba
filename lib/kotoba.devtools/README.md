# kotoba-lang/devtools

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-devtools`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Devtools: automation and inspection contracts for KAMI runtimes.
Does not capture screenshots or click real UI itself; defines semantic
element snapshots, automation plans/steps, synthetic input generation,
screenshot artifact metadata, and a UI/UX accessibility evaluator. Host
runtimes (e.g. `kami-web`) implement actual screenshot capture and
event injection using these shared contracts.

`InputEvent`/`Device` values are plain `:type`-tagged maps, duck-typed
to match `kotoba-lang/input`'s documented shapes.

## Status

Restored — ported from the original 553-line Rust `lib.rs`, with all 4
original Rust unit tests mirrored 1:1 in `test/devtools_test.cljk` (+1
smoke test) — 5 tests / 13 assertions, 0 failures. Pure data + pure
functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
