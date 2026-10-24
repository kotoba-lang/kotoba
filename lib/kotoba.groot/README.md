# kotoba-groot

[![CI](https://github.com/kotoba-lang/groot/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/groot/actions/workflows/ci.yml)

Clean-room **NVIDIA Isaac GR00T N1.x** foundation-policy compat surface, in
pure Clojure (`.cljc`). The "policy seat" of the KAMI embodied-AI stack —
embodiment/modality config, observation/action tensors, the policy
lifecycle, and a LeRobot-shaped episode record format.

This is a port of the Rust crate `kami-groot`
(`kotoba-lang/kami-engine`, ADR-0037) into a dedicated `kotoba.groot`
capability library per ADR-2607010000 (the `kami-engine` Rust workspace
is being retired in favor of pure Clojure "kotoba" authority repos, see
`com-junkawasaki/90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md`
in the superproject). No network, no I/O in the domain namespaces —
portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.

## Charter invariant

Mirrors the *public, documented* GR00T Vision-Language-Action API **by
name and shape only**. No NVIDIA library, header, binary, or model
weight is linked, vendored, or referenced (ADR-2605261800 section 2(b)
N1..N9 NEVER, inherited from the source crate). The seat is
embodiment-head-pluggable and the shipped default backend is
**KAMI-native** — a small affine policy (`a = W*obs + b`), so the whole
library builds, tests, and runs with **zero NVIDIA assets**.

## Surface (mirrored)

| GR00T N1.x | `kotoba.groot` | Notes |
|---|---|---|
| `Gr00tPolicy.from_pretrained(path, embodiment)` | `kotoba.groot.policy/from-pretrained` | no weights at `path` -> native backend |
| `policy.reset()` / `policy.get_action(obs)` | `policy/reset` / `policy/get-action` | native backend is stateless |
| `ModalityConfig` / embodiment data-config | `kotoba.groot.modality/{ModalityConfig,EmbodimentConfig}` | built from DOF names/limits + camera rig |
| obs `{state, video, language}` | `kotoba.groot.types/observation` | proprioception + frames + instruction slot |
| action chunk `[horizon, n_dof]` | `types/action` | action-chunking shape; native plan is myopic-tiled |
| new-embodiment head | `kotoba.groot.embodiment` (`native-head-*` + `act` multimethod) | swap native <-> out-of-tree checkpoint via `:head/kind` |
| LeRobot episode dataset | `kotoba.groot.episode/{episode,episode-step}` | clean-room schema, plain-EDN codec |

## Example

```clojure
(require '[kotoba.groot.modality :as modality]
         '[kotoba.groot.policy :as policy]
         '[kotoba.groot.types :as types])

(def emb
  (modality/embodiment-config
    "panda"
    ["j1" "j2" "j3" "j4" "j5" "j6" "j7"]
    (vec (repeat 7 [-2.9 2.9]))   ; per-DOF limits (from a URDF / sim get-dof-limits)
    ["wrist_cam"]
    16))                          ; action-chunk horizon

(def pol (policy/native emb))     ; zero NVIDIA assets

(def action
  (policy/get-action pol (types/observation (vec (repeat 7 0.0))
                                             :language "pick up the cube")))

(types/action-first action)       ; => [n-dof] joint targets to execute
```

## Build & test

```sh
kbb -M:test
kbb -M:lint
```

## Ported

All pure embodiment/episode/policy data-shape logic from the Rust crate:
`Frame`/`Observation`/`Action` (`kotoba.groot.types`), `ModalityConfig`/
`EmbodimentConfig` (`kotoba.groot.modality`), the `EmbodimentHead` seat
and `NativeHead` affine backend (`kotoba.groot.embodiment` +
`kotoba.groot.native`), the `Gr00tPolicy` lifecycle
(`kotoba.groot.policy`), and the `Episode`/`EpisodeStep` teleop record
format (`kotoba.groot.episode`). All Rust unit/integration tests
(`kami-groot/tests/native_backend.rs`) have `.cljc` parity tests here,
plus additional coverage for the individual constructors/accessors.

`kotoba.groot.native` also inlines the two pure functions the Rust crate
pulled from a sibling crate, `kami-shugyo`
(`LinearPolicy::{zeros,act_batch}` and `rescale_to_limits` from
`kami-shugyo/src/policy.rs`) — the affine math the native default
backend needs — including a parity test for
`rescale_maps_unit_interval_to_joint_limits`.

## Honestly still open / unported

- **`kami-shugyo` itself is out of scope.** Only the two pure functions
  above were inlined; the rest of `kami-shugyo` (vectorized env
  simulation, the gradient-free `random_search` trainer, `evaluate`,
  `Lcg`) is a separate RL-training-framework crate/port, not part of
  `kami-groot`'s surface.
- **The native default backend is a *small* learned policy, not a
  pretrained generalist** — it exists to make the seat real, testable,
  and baseline-able (unchanged from the Rust crate's own caveat).
- **Loading an actual GR00T checkpoint** (weight reader + tokenizer) is
  an explicit out-of-tree, host-adapter concern — GPU/OS/ML-runtime
  bridge code, deliberately not ported. `kotoba.groot.policy/with-backend`
  and the `kotoba.groot.embodiment/act` multimethod (dispatched on
  `:head/kind`) are the extension points a host adapter would hang off.
- **The `language` modality is a conditioning slot, not a trained LM**
  (unchanged from the Rust crate).
- **Camera frame pixel decoding/encoding** is not implemented —
  `kotoba.groot.types/frame` only carries the shape (`camera`/`width`/
  `height`/`pixels`); an actual video codec is a host-adapter concern.

## License

Apache License 2.0.
