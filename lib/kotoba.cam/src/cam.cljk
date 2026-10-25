(ns cam
  "Camera-rig domain logic: follow-cam, look-at constraint, and procedural
  shake.

  This is a **new implementation, not a restoration**. `cam` was
  registered on 2026-07-01 (`chore: scaffold kotoba-lang/cam CLJC`)
  claiming to restore a deleted `kami-engine/kami-cam` Rust crate as part
  of the clj-wgsl migration (ADR-2607010930) — but that claim does not
  hold up: the real `kami-cam` crate (recoverable from `kami-engine`'s git
  history) is CNC machining domain logic — G-code generation, toolpath
  simulation, tool library — with no camera code at all, and it has
  already been correctly ported to the sibling repo `kotoba-lang/cnc`
  (see `cnc/README.md`'s \"Origin\" section, which documents this
  discrepancy from the other side). `cam`'s registration appears to have
  been a naming collision: an unrelated, concurrent effort intended the
  name `cam` for **camera rigs** instead, also (mistakenly) claiming Rust
  restoration. There is no deleted camera-rig Rust source anywhere in this
  monorepo's history to restore, so the three namespaces below are
  genuinely new code closing that gap, not a port of anything.

    cam.follow          — exponential-smoothing follow-cam: tracks a
                           moving target position with a configurable
                           offset and damping factor
    cam.look-constraint — look-at basis construction (forward/right/up)
                           plus rotation-matrix-to-quaternion conversion
    cam.shake           — deterministic procedural camera shake with
                           amplitude/frequency/duration decay

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. Native
  execution (wgpu / wasmtime / wasmi, if/when this feeds a renderer) stays
  substrate; this repo owns only the CLJC contracts and math.")
