> **Renamed 2026-07-10 (ADR-2607102200 addendum):**
> `kami-script-runtime` → `kami-input-map` → **`kami-engine-input-map`**
> (`kami-engine-*` family; device-neutral stick/deadzone, not the full WASM host).

> **Renamed 2026-07-10 (ADR-2607102200):** `kotoba-lang/kami-script-runtime` → `kotoba-lang/kami-input-map`.
> Old GitHub URLs redirect. See root ADR for the full authority/deps map.

# kami-script-runtime (input_map only)

This repo is a **deliberately partial** restoration — it ports exactly one
file from the legacy `kami-script-runtime` Rust crate, not the crate as a
whole.

## Background

`kami-script-runtime` was a WASM host in `kotoba-lang/kami-engine`: it ran
guest `.clj`/component-model code via `wasmtime` (JIT) or `wasmi` (no-JIT
fallback), binding the `kami:engine/*` imports to live Rust game-engine
state. Its Rust workspace was deleted in kotoba-lang/kami-engine PR #82, and
is recoverable at commit `a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`.

Per ADR-2607010930, this project restores deleted Rust crates as
zero-dependency portable `.cljc` — but only where a genuinely portable
representation exists. `kami-script-runtime` as a whole does not qualify:
`src/lib.rs`, `src/platform.rs`, and `src/bin/*` are the actual WASM host —
they bind to `wasmtime`/`wasmi`, the filesystem, and native game-engine
state. That is substrate, not logic, and this project's AGENTS.md and
standing ADR explicitly exclude it from restoration. **None of that is
ported here, and none of it will be.**

## What *is* ported

`src/input_map.rs` is different. Its own doc comment says it plainly:

> device-neutral input mapping (ADR-0037 seam #3)... in pure Rust... This
> module has no platform deps and is fully unit-tested.

It's a self-contained pure-math module — translating raw device input
(on-screen touch sticks, physical analog sticks, button held-sets) into the
abstract `kami:engine/input` surface (`(axis "MoveX")`, `(key-pressed?
"Fire")`) that guest code actually calls. No engine state, no I/O, no
platform deps — just arithmetic and set operations. That makes it the one
piece of this otherwise-substrate crate worth porting.

Ported to [`src/input_map.cljk`](src/input_map.cljk) (namespace
`input-map`), 1:1 with the original Rust:

- **`stick` / `axes`** — port of `VirtualStick::new` / `VirtualStick::axes`.
  An on-screen thumbstick: a touch point is mapped to a clamped `[-1, 1]`
  axis pair (**y up**), with a radial dead zone and smooth rescaling past
  it.
- **`apply-dead-zone`** — port of `apply_dead_zone`. Radial dead zone +
  unit-circle clamp for a physical analog stick.
- **`button-edges` / `update`** — port of `ButtonEdges::new` /
  `ButtonEdges::update`. Computes press/release edges from a per-frame
  "held" set of action names, host-side, so `key-down?` (level) and
  `key-pressed?` (edge) read identically on every platform. (`update`
  returns `[edges updated-detector]` rather than mutating in place, since
  CLJC favors immutable data over the original's `&mut self`.)

Line count: `src/input_map.cljk` is ~140 lines (vs. ~185 lines in the
original `input_map.rs`, doc comments included).

## Tests

[`test/input_map_test.cljk`](test/input_map_test.cljk) ports every original
Rust `#[test]` 1:1 (`button_press_is_an_edge`,
`button_edges_track_multiple_actions`, `stick_center_is_zero`,
`stick_dead_zone_reads_zero`, `stick_full_right_is_plus_x`,
`stick_up_is_plus_y`, `stick_clamps_beyond_radius`,
`dead_zone_gates_small_input`, `dead_zone_clamps_to_unit_circle`), plus a
namespace-loads smoke test.

**10 tests, 21 assertions, 0 failures, 0 errors.**

```
kbb -M:test
```

## What's excluded (and won't be ported)

- `src/lib.rs` — the `KamiScriptRuntime` WASM host: instantiates the
  `wasmtime`/`wasmi` engine, wires `kami:engine/*` component imports to
  live game-engine state, drives `feed_stick` per frame.
- `src/platform.rs` — native platform glue (windowing/OS integration).
- `src/bin/*` — native binaries.

These require a real WASM runtime and live, mutable engine state — there is
no meaningful "portable pure-data" representation of a JIT compiler binding
to a running game world. This is intentional and permanent scope exclusion,
not a TODO.
