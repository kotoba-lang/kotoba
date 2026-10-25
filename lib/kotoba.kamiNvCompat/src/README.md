# @etzhayyim/kami-nv-compat

**Drop-in NVIDIA Omniverse stack API-compat facade**, consumed by `@etzhayyim/sdk`
and other KAMI-based clients as a standalone package.

**Status**: R1.0 path reservation (ADR-2605261800). Relocated 2026-07-01 from
`etzhayyim/root:20-actors/etzhayyim-sdk/src/nv-compat/` to `kotoba-lang/kami-nv-compat`
per the org-taxonomy library-placement rule (ADR-2606302300).

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
| R1.1 | `isaac-sim.ts` ✅ (isaacsim.core.api facade → `e7m-sim`: World sim-context + Articulation (PD targets / efforts / FK) + RigidPrim, over the Featherstone articulated-dynamics module) |
| R1.2 | `optix.ts` ✅ (OptiX® C-style facade → `kami-rt` WebGPU/WGSL ray tracer + CPU fallback); `rtx-renderer.ts` ✅ (RTX Renderer® facade → `kami-rtx` WGSL Monte-Carlo path tracer + CPU fallback) |
| R1.3 | `omni-replicator-core.ts` ✅ (Replicator DR + writers facade → `utsushimi` engine: bit-reproducible LCG sampler, distributions, scatter/material DR, COCO/Kitti writers, real 2D boxes via kami-rt projection) |
| R1.4 | `omni-usd.ts` ✅ (pxr.Usd / UsdGeom facade → `kami-usd` USDA reader + scene bridge → kami-rt / kami-rtx); `omni-kit-app.ts` ✅ (omni.kit.app / commands facade → `amenominaka`: IExt + extension.toml + dependency-ordered Application lifecycle + undo/redo command stack; hosts the USD→render pipeline) |
| R1.5 | `isaaclab-envs.ts` ✅ (isaaclab.envs / managers facade → `e7m-shugyo`: manager framework + classic Cartpole `ManagerBasedRLEnv`, single + vectorized Gym loop) |
| R1.6 | `drive-sim.ts` ✅ (DRIVE Sim facade → `wadachi-sim`: scenario world + camera/LiDAR/radar sensor models grounded in kami-rt, closed-loop with the Alpamayo model, USD→scenario bridge) |
| R1.7 | `omni-cloud.ts` ✅ (Omniverse Cloud facade → `murakumo-render`: render-farm job queue over kami-rt/kami-rtx, turntable batch + streaming; Murakumo-fleet-only) |
| R1.9 | `omni-nucleus.ts` ✅ (omni.client / Nucleus facade → `kotoba-datomic-nucleus`: content-addressed append-only versioned store + checkpoints + change subscriptions) |

**R1 Omniverse stack: all 9 sub-phases landed.** USD (R1.4) → Nucleus store (R1.9) → Cloud render farm (R1.7) over OptiX/RTX (R1.2), with Replicator synthetic data (R1.3), Isaac Lab RL envs (R1.5), DRIVE Sim sensors (R1.6) + the Kit app shell (R1.4) hosting it all.

## Alpamayo AV stack (separate NVIDIA AV product, not Omniverse)

Clean-room API-compat for the [NVIDIA Alpamayo](https://www.nvidia.com/en-us/solutions/autonomous-vehicles/alpamayo/)
reasoning VLA family for autonomous vehicles. Canonical KAMI engines per
`ALPAMAYO_COMPAT_MAP`. Civilian, **SAE-L4 ceiling**, **sim-only (no
actuation)**, **Murakumo-only** language inference (ADR-2605215000); AV scope
per ADR-2605242000 (wadachi) / ADR-2606010600 (kami-autodrive).

| Module | Mirrors | Canonical engine |
|---|---|---|
| `alpamayo.ts` ✅ | Alpamayo-R1 VLA (`from_pretrained`/`predict`: multi-cam + nav + egomotion → 6.4 s / 64-wp ego trajectory + Chain-of-Causation) | `michibiki` (kami-drive) |
| `alpasim.ts` ✅ | AlpaSim / AlpaGym closed-loop rollout + reward | `wadachi-sim` |
| `kami-drive/` ✅ | BEV unicycle kinematics + reasoning planner + CoC schema (+ kotoba `:coc/*` datom bridge) | `michibiki` |

## License

Apache 2.0 + Charter Compliance Rider v3.6 (`/CHARTER-RIDER.md`).
