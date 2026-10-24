# kotoba-lang/input

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-input`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Input: unified input system domain interpreter — action mapping
(keyboard/mouse/touch/gamepad → abstract `Action`), gesture detection
(pinch/swipe/tap), and multi-panel focus routing. Ledger class
`:port-to-CLJC-domain-interpreter` — native event capture stays
host-side; this namespace owns the platform-agnostic logic that
consumes those raw events.

## Status

Restored — the single-namespace input interpreter ported from the
original 429-line Rust `lib.rs`, with all 3 original Rust unit tests
mirrored 1:1 in `test/input_test.cljk` (+1 smoke test) — 4 tests / 12
assertions, 0 failures. Pure data + pure functions throughout; no
IO/GPU. `pop-modal` returns `[popped-panel-or-nil fm']` rather than
Rust's `&mut self` mutation.

## Develop

```bash
kbb -M:test
```
