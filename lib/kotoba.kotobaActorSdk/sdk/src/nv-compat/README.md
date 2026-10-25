# @etzhayyim/sdk/nv-compat

**Drop-in NVIDIA Omniverse stack API-compat facade** for `@etzhayyim/sdk`.

**Status**: R1.0 path reservation (ADR-2605261800).

## Purpose

This namespace exposes the **public, documented API surface** of NVIDIA Omniverse
Kit / Isaac Sim / Isaac Lab / OptiX / RTX Renderer / Replicator / DriveSim /
Omniverse Cloud / Nucleus so that existing TypeScript code targeting those APIs
can be ported with **import-path-only changes** to run on KAMI + WebGPU + WASM
(canonical implementations under `40-engine/kami-engine/kami-*`).

## Trademark notice

NVIDIA®, Omniverse®, Isaac®, OptiX®, RTX®, Nucleus®, DriveSim® are trademarks
of NVIDIA Corporation. This project is not affiliated with or endorsed by NVIDIA.
The NVIDIA names appearing within this namespace are used solely as **API
compatibility identifiers** (per Google v. Oracle, 593 U.S. ___ (2021)).

Canonical KAMI implementations have distinct names (see `nv-compat-map.json`
when generated): `amenominaka` / `e7m-sim` / `e7m-shugyo` / `hikari-rt` /
`kami-rtx` / `utsushimi` / `wadachi-sim` / `murakumo-render` / `kotoba-datomic-nucleus`.

## Scope (intentionally limited)

- ✅ Public, documented Python / TS API surface (Omniverse Kit Public API docs,
  Isaac Sim docs, Isaac Lab docs, Replicator docs)
- ❌ Private / undocumented / internal `omni.*` modules
- ❌ Binary SDK linking, header copy, asset bundle redistribution

## R1 sub-phase delivery

| Sub-phase | Module |
|---|---|
| R1.1 | `isaacsim/core/api/{World, Articulation, RigidPrim}.cljc` |
| R1.2 | `optix.cljc`, `rtx-renderer.cljc` |
| R1.3 | `omni-replicator-core.cljc` |
| R1.4 | `omni-usd.cljc`, `omni-kit-app.cljc` |
| R1.5 | `isaaclab/envs/{ManagerBasedRLEnv}.cljc` |
| R1.6 | `drive-sim.cljc` |
| R1.7 | `omni-cloud.cljc` |
| R1.9 | `omni-nucleus.cljc` |

## License

Apache 2.0 + Charter Compliance Rider v2.0 (`/CHARTER-RIDER.md`).
