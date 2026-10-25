# kotoba-lang/cam

Zero-dep portable `.cljc` — camera-rig domain logic: follow-cam, look-at
constraint (with quaternion output), and procedural shake.

## Not a restoration — a correction

This repo was originally registered (2026-07-01, `chore: scaffold
kotoba-lang/cam CLJC`) claiming to restore a deleted
`kami-engine/kami-cam` Rust crate, as part of the clj-wgsl migration
(ADR-2607010930). **That claim was wrong.** The real `kami-cam` crate
(still recoverable from `kami-engine`'s git history) is CNC machining
domain logic — G-code generation, toolpath simulation, a cutting-tool
library — with no camera code in it at all. That crate has already been
correctly ported to the sibling repo
[`kotoba-lang/cnc`](https://github.com/kotoba-lang/cnc); see that repo's
[README "Origin" section](https://github.com/kotoba-lang/cnc#origin) for
the full account, including how it flagged this very naming collision
from the other side.

`cam`'s registration appears to have been an accidental naming collision:
an unrelated, concurrent effort intended the name `cam` for **camera
rigs** instead (follow-cam / look-constraint / shake — the capabilities a
completeness-audit report inferred from this repo's own scaffold
docstring), also mistakenly claiming Rust restoration. There is no
deleted camera-rig Rust source anywhere in this monorepo's history to
restore.

**This repo is therefore a new implementation, not a port**, closing the
gap left by that mistaken/abandoned scaffold registration.

## Namespaces

| Namespace | Purpose |
|---|---|
| `cam` | Aggregator/docs namespace |
| `cam.follow` | Follow-cam: exponential-smoothing tracking of a moving target, with a configurable positional offset and damping factor |
| `cam.look-constraint` | Look-at basis construction (`forward`/`right`/`up`) and rotation-matrix-to-quaternion conversion |
| `cam.shake` | Deterministic procedural camera shake (amplitude/frequency/duration) for impact/damage feedback |

No network, no I/O, no GPU — pure data and functions only, portable
across JVM / ClojureScript / SCI / GraalVM-WASM. No external
vector/linalg dependency: each namespace inlines the handful of 3-vector
operations it actually needs rather than pulling in a shared math
library.

## Usage

```clojure
(require '[cam.follow :as follow]
         '[cam.look-constraint :as lc]
         '[cam.shake :as shake])

;; follow-cam: chase a target with an offset, smoothed over time
(let [cfg (follow/follow-config [0.0 2.0 -5.0] 0.15)]
  (follow/update-follow [0.0 0.0 0.0] [10.0 0.0 0.0] cfg 0.016))
;; => a camera position partway from [0 0 0] toward [10 2 -5]

;; look-at constraint: orient a camera toward a target, get a quaternion
(let [basis (lc/look-at [0.0 0.0 0.0] [1.0 0.0 0.0] [0.0 1.0 0.0])]
  (lc/basis->quaternion basis))
;; => [0.7071067811865476 0.0 -0.7071067811865475 0.0]

;; procedural shake: a decaying positional jitter after an impact
(let [cfg (shake/shake-config 0.5 6.0 0.4)]
  (shake/shake-offset cfg 0.1 42))
;; => a [x y z] offset, shrinking to [0.0 0.0 0.0] by elapsed-time 0.4
```

## Design notes

- **`cam.follow`** uses the frame-rate-independent exponential-smoothing
  factor `1 - exp(-rate * dt)`, remapping the `(0 1]` `:damping` knob to a
  decay rate `damping / (1 - damping)` so that `damping = 1.0` means an
  exact instant snap (special-cased to avoid a division by zero at the
  boundary). See the `smoothing-alpha` docstring for the frame-rate-
  independence argument and its limits.
- **`cam.look-constraint`** builds the basis with the standard
  forward/right/up cross-product construction and converts it to a
  quaternion with Shepperd's branch-on-largest-diagonal method (stable
  across all orientations, unlike the naive trace-only formula). The
  degenerate case (target directly above/below the eye, forward parallel
  to `up`) falls back to a different reference axis rather than dividing
  by ~0.
- **`cam.shake`** uses a small deterministic sine-based function as a
  *simplified stand-in* for real Perlin/simplex noise — same output for
  the same `(elapsed-time seed axis-index frequency)`, different-looking
  per axis, but with none of the spatial/temporal coherence guarantees of
  actual noise. See the `axis-noise` docstring for why the phase is fed
  to `sin` directly in radians rather than normalized to cycles first (a
  `2*pi` normalization was tried and silently cancelled out the integer
  `seed`/`axis-index` terms via `sin`'s periodicity — caught by the tests
  in `cam.shake-test`, not by inspection).

## Status

New implementation, complete for the three capabilities named above.
`kbb -M:test`: **17 tests, 37 assertions, 0 failures, 0 errors.**

Not implemented (out of scope for this pass, no existing spec to match
against since there's no legacy source): multi-target/weighted follow,
spring-damper (as opposed to exponential) follow physics, slerp/quaternion
output from `cam.follow`, shake presets, or noise upgraded to real
Perlin/simplex.

## Develop

```bash
kbb -M:test
```

## License

Apache License 2.0.
