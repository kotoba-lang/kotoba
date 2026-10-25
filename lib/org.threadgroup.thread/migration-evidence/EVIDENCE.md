# thread.frag whole-component migration evidence (tick 9, 2026-09-04)

Authority: lang/q9-migration.edn v3 (:whole-component-build-contract) +
ADR-q9-whole-component-build-migration.md.

## Scope decision — split disposition candidate, NOT whole-component migration yet

`org-threadgroup-thread` has 4 namespaces (frag 98, dispatch 41, mesh 115,
iphc 411 lines). This tick's evidence covers **thread.frag** as a
`guest-entry` slice per the `:split` disposition (whole-component-guest-entry
+ declared imports/exports); iphc/mesh/dispatch remain in `.cljc` (iphc needs
atoms/`swap!`/`bit-test`/`case`/`subvec` — measured not in the admitted
subset; mesh needs atoms + loops). Per authority, a split migration only
counts when the guest entry covers a declared component boundary — so this is
recorded as **evidence toward split, not a completed migration**.

## Source

- Guest entry: `src/thread/frag.kotoba` — hand-port of all 4 public exports
  (build-frag1, build-fragn, parse-frag1, parse-fragn) + main.
- Encoding constraints of the admitted subset (amu d90665c7):
  - `:ok`/`:error` keyword tags → leading integer status code (1 = ok, 0 = error;
    reason distinguishable per the documented mapping since each fn has ≤1 error kind
    per arg position).
  - `bit-shift-left`/`unsigned-bit-shift-right` → `* 256` / `quot x 256` (both admitted).
  - `:keys` destructure of typed maps → plain i64 params (parse fns take bytes as
    separate params; build fns take fields directly — API shape change declared here).

## Gates (all JVM-free; JAVA_HOME unset; descendants traced = node/sh only, no JVM)

| Gate | Command | Result |
|---|---|---|
| amu check | `amu check --jvm-free src/thread/frag.kotoba` | PASS (tfe-c.out:ok true) |
| amu compile wasm32 | `amu compile ... --target wasm32 --jvm-free --output` | PASS, provenance + publication sidecars (tfe-c.out) |
| kotoba check | `bin/kotoba check --safe src/thread/frag.kotoba` | PASS :check/valid (tfe-k2.out) |
| kotoba compile | `bin/kotoba compile ... --target wasm --output` | PASS :compile/emitted (tfe-k4.out) |
| package build | `kotoba rad build --project /tmp/q9-frag --profile release` | PASS :rad/executed, q9_frag.wasm emitted |
| amu inspect | `amu inspect ... --output` | PASS, exports/param-types recorded (c13i.out) |
| artifact equivalence | sha256(amou wasm32) == sha256(kotoba wasm) | **4c81bcde…24a identical** |
| oracle parity | nbb (JVM-free CLJS) golden vs port semantics | 15/15 vectors matched (parity.out) |
| JVM-free process proof | descendant walk of amu + kotoba runs | NONE (jvm-proof2.txt, jvm-proof5.txt) |

Note: amu `--target aarch64` is target-rejected for typed vector results
("typed values currently require … kotoba-script web target, typed Wasm target,
or qualified native … features") — per authority, that route is
blocked-for-now, not worked around. wasm32/wasm are the declared targets.

Note: `amu test` (kotoba-script runtime) fails with "unsupported KIR
operation" on the vector-returning defs — runtime execution path is not yet
available for this shape; parity was verified via the nbb oracle + the
integer semantics model instead (recorded honestly as a gap).

## Open gaps before this can be called a completed migration

1. `amu test` runtime execution unsupported for vector results.
2. mesh.cljc (atoms, loops) and iphc.cljc (atoms, `case`, `bit-test`,
   `contains?` on keyword maps, `subvec`) not representable in the admitted
   subset — the component-level split record needs a declared
   capability/import design for these.
3. `dispatch.cljc` is portable (bit-and/quot only) but returns keywords —
   same keyword-return encoding question as frag (solved here with status
   codes, needs API decision sign-off).
