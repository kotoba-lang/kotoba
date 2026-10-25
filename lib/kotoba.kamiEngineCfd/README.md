# kotoba-lang/kami-engine-cfd

Zero-dep portable `.cljc` — a clean-room D2Q9/D3Q19 lattice-Boltzmann (LBM)
CFD solver, migrated in place from this repo's own Rust crate, per the
repo-wide Rust-demotion / clj-wgsl-migration runtime priority
(`com-junkawasaki/root` `AGENTS.md`, ".cljc/.kotoba ランタイム優先順位"
section, 2026-07-10 revision) and following the precedent of
**ADR-2607010930 "clj-wgsl migration"** (`com-junkawasaki/root`), the same
migration that produced sibling repos `kotoba-lang/mesher`, `pnr`, `rtl`,
and `ic-packaging`.

## Status: migrated in place (not restored from a deletion)

Unlike `mesher`/`pnr`/`rtl` — whose source Rust crate lived in
`kotoba-lang/kami-engine` and was deleted outright before being restored as
CLJC — **`kami-engine-cfd` was never deleted**. Its history has an extra
wrinkle worth being explicit about:

- **2026-06-28 - 2026-07-01**: the Rust LBM solver was built up in several
  stages (D2Q9 -> D3Q19 -> parallelised -> Smagorinsky LES -> free-slip
  boundaries -> real-geometry voxelisation via STL/Ahmed-body meshing).
  Design rationale is in `docs/adr/0001-lbm-solver.md`.
- **2026-07-01** (commit `755fa13`, "Remove Rust runtime from CFD
  contract"): the Rust source (`Cargo.toml`, `src/*.rs`, `tests/*.rs`) was
  deleted and replaced with an EDN-contract-only design —
  `src/kami_engine/cfd/contract.cljk` (request/result *shape* validators,
  see below) — with a stated intent that "LBM/RANS/LES/GPU/native/remote
  solvers live in separate adapter repositories." **No adapter repository
  implementing the actual solver math was ever built.** The Rust removal
  left the LBM solver itself unimplemented anywhere; only its EDN schema
  was validated.
- **This migration** (branch `cfd-cljc-migration`) recovers the
  pre-deletion Rust source from git history (commit `2958ba8`, the parent
  of `755fa13`) and ports it faithfully to portable `.cljc`, completing
  what the 2026-07-01 commit should have done under the repo's actual
  runtime policy: the Rust gets demoted, but the solver itself is *ported*,
  not left unimplemented. `src/kami_engine/cfd/contract.cljk` is
  unrelated/complementary and is left as-is — it validates request/result
  EDN *shapes*; the namespaces below compute the actual physics those
  shapes describe. `docs/adr/0001-lbm-solver.md` is kept (with a short
  addendum note below) rather than deleted, since it is design history, not
  Rust code.

## What was ported

| Namespace | Ported from (original Rust) | Lines (orig -> cljc) | Purpose |
|---|---|---|---|
| `kami-cfd` | `src/lib.rs` (209) | 209 -> 201 | Clean-room D2Q9 (2D, 9-velocity) single-relaxation-time BGK LBM solver: `block`/`teardrop` bodies, `lbm-new`/`step`/`run`, `sectional-cd` |
| `kami-cfd.mesh` | `src/mesh.rs` (65) | 65 -> 136 | Binary STL triangle-soup parser (`parse-stl`, portable pure-arithmetic little-endian decoder) + Ahmed-body bluff-body generator (`ahmed-body`) |
| `kami-cfd.d3` | `src/d3.rs` (376) | 376 -> 335 | D3Q19 (3D, 19-velocity) LBM + Smagorinsky LES subgrid turbulence + free-slip far-field / no-slip road boundaries; `box-car`/`fastback-car`/`from-triangles` bodies, `vehicle-cd` |
| `kami-cfd.runner` (`.clj`, JVM-only) | `src/main.rs` (70) | 70 -> 69 | Optional CLI, nice-to-have per the migration plan — mirrors `kotoba-lang/plm`'s conservative host-runner pattern |
| `test/kami_cfd_test.cljk` | `tests/drag.rs` + `tests/drag3d.rs` + `tests/mesh.rs` (36+31+51=118) | 118 -> ~150 | All 8 original `#[test]`s ported 1:1, `clojure.test`, docstring-provenance style |

Total original Rust `src/` + `tests/`: 838 lines. `src/main.rs` was a
nice-to-have per the migration plan (not required), but was ported anyway
since it was small and completed the CLI story.

## Design choices specific to this port

- **Mutable arrays, not persistent vectors, for the hot solver state.** The
  9-velocity (`kami-cfd`) / 19-velocity (`kami-cfd.d3`) per-cell
  distribution buffers (`f`/`ftmp`) and each body's `solid` mask are backed
  by `double-array`/`boolean-array`/`int-array` (`aget`/`aset`), mirroring
  the original Rust `Vec<f64>`/`Vec<bool>` buffers directly. This is a
  deliberate performance choice: collide/stream touches every cell every
  step across hundreds to thousands of steps, and persistent-vector copies
  would make that O(cells) per step instead of O(1). These array
  primitives are portable across JVM Clojure, ClojureScript, and nbb. The
  `Lbm`/`Lbm3`/`Body`/`Body3` values themselves are plain immutable maps
  threading these mutable buffers through — "swapping f/ftmp" (the
  original Rust `std::mem::swap`) is a cheap `assoc` of array references,
  not a data copy.
- **STL binary parsing is pure arithmetic — no reader conditionals
  needed.** The original Rust `parse_stl` used `u32::from_le_bytes`/
  `f32::from_le_bytes`. Rather than branching on `java.nio.ByteBuffer`
  (`:clj`) vs `js/DataView` (`:cljs`), `kami-cfd.mesh` decodes little-endian
  u32 via `+`/`*` (never touching the sign bit of a host 32-bit int on
  either platform) and IEEE-754 f32 via pure integer arithmetic on the
  sign/exponent/mantissa bit fields (`quot`/`rem`, no
  `Float/intBitsToFloat` / `DataView.getFloat32`; even the power-of-two
  scaling is a small manual multiply/divide loop, no `Math/pow`). No
  sibling repo (`kotoba-lang/step`, `dxf`) had an existing binary-parsing
  convention to reuse — both are ASCII formats. `kotoba-lang/pnr`'s
  `pnr.gdsii` *writes* binary GDSII JVM-only via `java.io`, which doesn't
  fit a portable *parser* either. The pure-arithmetic approach needed zero
  platform branches and is the simpler fallback the migration guidance
  favours when no house convention exists.
- **`std::thread::scope` parallelism was deliberately dropped, not
  ported.** The original `d3.rs` split `collide_parallel`/
  `stream_drag_parallel` across native OS threads (safe because collide is
  per-cell independent and the "pull"/gather streaming form makes each
  cell write only its own output — no write conflicts). `kami-cfd.d3`'s
  `collide!`/`stream-drag!` keep the exact same math and the exact same
  pull/gather streaming form — chosen deliberately in the original
  design — just iterated as a single sequential loop instead of split
  across threads. This is a deliberate, documented trade, not an
  oversight: portability across JVM Clojure / ClojureScript / nbb takes
  priority over multi-threaded performance per repo policy, and native OS
  threads have no clean portable equivalent across those three hosts.
- **`docs/adr/0001-lbm-solver.md` is kept, not deleted.** It documents the
  physics design and the calibration journey (D2Q9 -> D3Q19 -> LES ->
  free-slip boundaries -> real-geometry voxelisation) — none of that
  changed in this migration, only the host language did. It already
  carries a "Superseded as in-repo runtime (2026-07-01)" status note from
  the earlier Rust-removal commit; this migration does not edit that
  historical note (doing so would misrepresent what was decided and when),
  but this README is the authoritative statement of the *current* status:
  the solver *is* implemented in-repo again, as portable CLJC.

## Test step-count / grid-size reductions (JVM performance, not weakened physics)

Interpreted JVM Clojure without hand-unrolled/AOT numeric code is roughly
1-2 orders of magnitude slower per lattice-cell-step than native Rust.
Running every original test unchanged (some simulate hundreds of thousands
of cells for 1000-3000 steps — billions of inner-loop iterations) would
make a single `kbb -M:test` run take on the order of an hour.
`test/kami_cfd_test.cljk` ports all 8 original tests with the same physical
assertions, but:

- The 3 ported `tests/drag.rs` (2D) tests keep the original 240x80 grid and
  cut step counts by roughly half (2500->1000, 3000->1200, 2500->1000) —
  the wake structure these tests check is already resolved well before
  that, and the assertions are order comparisons (`block > teardrop`,
  `finite && positive`), not exact absolute Cd values.
- The 2 ported `tests/drag3d.rs` tests, plus the one `tests/mesh.rs` test
  that actually runs the LES solver (`ahmed-slant-reduces-drag` — as
  opposed to pure voxelisation), shrink the domain and body proportionally
  (same blockage ratio, same relative body shape) in addition to cutting
  steps — e.g. `high-re-stable-with-les`'s domain goes from 96x40x28 to
  48x20x14 (1/8 the cells) with the body halved on every axis to match.
  This preserves the qualitative physics being demonstrated (LES keeping
  high-Re BGK finite/stable, fastback beating squareback, a slanted rear
  beating a squareback) at a cell count the JVM churns through in seconds
  instead of minutes — verified empirically before committing to these
  parameters (fastback 3.443 < box 3.544 at the reduced scale; slant beats
  squareback at the reduced scale; see test file for the actual numbers).
- `mesh-voxelises-to-a-solid` and `stl-roundtrips` do no LBM stepping at
  all (pure voxelisation / byte parsing), so they keep the **original**
  Rust grid sizes (140x64x40) unchanged — voxelisation alone is cheap
  regardless of grid size (milliseconds).

Every reduction is called out inline in `test/kami_cfd_test.cljk`'s
docstrings, next to the original Rust value it replaces. No assertion's
*physics* was weakened — only the resolution/step-count used to
demonstrate it.

## Verify

```bash
kbb -M:test
```

`Ran 11 tests containing 25 assertions. 0 failures, 0 errors.` — 8 tests /
14 assertions from the new `kami-cfd-test` (all 8 ported Rust `#[test]`s),
plus the pre-existing 3 tests / 11 assertions from
`kami-engine.cfd.contract-test` (unmodified except for a dead `-main`
removal now that `deps.edn` uses the shared `cognitect.test-runner`
alias — see below). `kbb -M:test:cljc` runs the same suite via babashka as a
smoke check.

## Repo layout

| path | role |
|---|---|
| `src/kami_cfd.cljk` | 2D D2Q9 LBM solver |
| `src/kami_cfd/mesh.cljk` | Binary STL parser + Ahmed-body generator |
| `src/kami_cfd/d3.cljk` | 3D D3Q19 + Smagorinsky LES solver |
| `src/kami_cfd/runner.cljk` | Optional JVM CLI |
| `src/kami_engine/cfd/contract.cljk` | EDN request/result shape validators (pre-existing, unrelated) |
| `test/kami_cfd_test.cljk` | All 8 original Rust `#[test]`s, ported 1:1 |
| `test/kami_engine/cfd/contract_test.cljk` | Contract validator tests (pre-existing) |
| `docs/adr/0001-lbm-solver.md` | Original physics design rationale — still accurate, only the host language changed |

`deps.edn` follows the same `{:paths ["src" "test"] :aliases {:test
{...cognitect.test-runner...}}}` shape as `kotoba-lang/mesher`/`pnr`/`rtl`,
replacing the previous ad hoc `-main`-based test entry point (now redundant
with `cognitect.test-runner`'s auto-discovery of `*-test` namespaces under
`test/`).

## EDN contract shapes (pre-existing, unrelated to the solver above)

`src/kami_engine/cfd/contract.cljk` validates the request/result EDN shapes
a `:lbm` cae-solver method sends/receives — unmodified by this migration.
Requests describe solver intent:

```edn
{:kami.cfd/solver :lbm
 :kami.cfd/dim 3
 :kami.cfd/geometry :ahmed
 :kami.cfd/reynolds 3000.0
 :kami.cfd/steps 1500}
```

Results describe solver output:

```edn
{:kami.cfd/solver :lbm
 :kami.cfd/dim 3
 :kami.cfd/geometry :ahmed
 :kami.cfd/vehicle-cd 0.29
 :kami.cfd/steps 1500
 :kami.cfd/status :ok}
```

`kami-cfd.d3/vehicle-cd` and `kami-cfd/sectional-cd` above are exactly the
kind of computation these EDN shapes describe the inputs/outputs of; wiring
a `kami-cfd.d3`-backed adapter that produces `contract.cljc`-conformant
results is a natural next step, out of scope for this migration.
