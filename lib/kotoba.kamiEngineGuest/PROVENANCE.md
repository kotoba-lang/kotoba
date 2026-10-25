# Provenance

This directory was consolidated from the standalone `kotoba-lang/engine` repo
(final commit `e8bb9afc7fd85f8ae044026f5a20c986d0bae42c` before the move) back
into `kami-engine`.

Rationale: `kotoba-lang/engine` is the CLJ→WASM compiler this project calls
`kami-engine-clj` (its name before the clj-wgsl migration extracted it into
its own repo, ADR-2607010930). It contains zero Rust source. `kami-engine`'s
CI enforces a no-Rust guard across the whole repo, and `kami-engine-clj` has
none — so it fits `kami-engine`'s current role as the CLJ/EDN/WIT asset-and-
contract home without violating that guard, unlike `kami-clj-play` and
`kami-script-runtime-rs`, which contain real Rust and correctly remain
separate standalone repos.

The standalone `kotoba-lang/engine` repo is archived (not deleted) as of this
move; its README points here.
