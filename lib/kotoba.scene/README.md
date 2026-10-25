# kotoba-lang/scene

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-scene` Rust crate
(deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace from kami-engine")
as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

KAMI Scene: tolerant EDN accessor helpers for the Datomic-shaped `scene.edn` a
kami-clj game ships (ADR-0036). Native players (`kami-clj-play`/`kami-clj-play3d`)
parse the *same* tolerant way: missing keys fall back to defaults rather than
erroring, namespaced keywords match on `ns/name`, and numbers coerce int<->float.

Unlike the original (which hand-parsed EDN via `kotoba_edn::EdnValue` since Rust has
no native EDN reader), this namespace parses via Clojure's own `clojure.edn/read-string`
— keys are already real keywords, so `kw-key`/`mget` operate directly on them rather
than on a parsed-value wrapper type.

**Not to be confused with** `kotoba-lang/kami-scene-contracts` (a separate repo,
authority for the `:scene-domains` provider family).

## Status

Restored — ported from the original 103-line Rust `lib.rs`, with all 5 original Rust
unit tests mirrored 1:1 in `test/scene_test.cljk` (+1 smoke test) — 6 tests / 19
assertions, 0 failures. Pure data + pure functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
