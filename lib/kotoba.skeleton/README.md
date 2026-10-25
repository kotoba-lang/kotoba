# kotoba-lang/skeleton

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-skeleton`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Skeleton: glTF-compatible skeletal animation — bone hierarchy,
keyframe interpolation (linear/step/cubic-spline), pose blending/
cross-fade, CCD inverse kinematics, anatomical joint constraints, and
bone-name retargeting. Ledger class `:port-to-CLJC-domain-interpreter`
— GPU skinning (consuming the joint-matrix buffer this namespace
produces) stays native/WGSL; this namespace owns the animation math and
pose evaluation itself.

| Namespace | Purpose |
|---|---|
| `skeleton` | Bone/Skeleton/AnimationClip, pose evaluation, blending, CCD IK, joint constraints, retargeting |
| `skeleton.math` | Minimal Vec3/Quat/Mat4 math (glam-compatible conventions), needed since Rust's `glam` has no CLJC equivalent |

## Status

Restored — ported from the original 892-line Rust `lib.rs`. All 12
original Rust unit tests mirrored 1:1 in `test/skeleton_test.cljk` (+1
smoke test, + 1 constructor helper reused across tests counted
separately by the test runner) — 15 tests / 37 assertions, 0 failures.
Pure data + pure functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
