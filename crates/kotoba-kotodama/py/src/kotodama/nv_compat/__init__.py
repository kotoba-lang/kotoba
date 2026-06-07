"""kotodama.nv_compat — NVIDIA Omniverse stack public-API drop-in compat facade.

Per ADR-2605261800 §D5: NVIDIA family public APIs (Omniverse Kit, Isaac Sim,
Isaac Lab, OptiX, RTX Renderer, Replicator, DriveSim, Omniverse Cloud, Nucleus,
PhysX) are mirrored under this namespace so existing scripts port with
import-path-only changes.

Canonical implementations are in 40-engine/kami-engine/kami-* (Rust + WebGPU
+ WASM). Pure-Python equivalents in this namespace track the Rust contracts
formula-for-formula and are intended for Pyodide / native CPython use; the
formulas are unit-tested against the Rust crates via parallel test fixtures
(40-engine/kami-engine/fixtures/cartpole/).

Trademark notice: NVIDIA®, Omniverse®, Isaac®, OptiX®, RTX®, Nucleus®,
DriveSim®, PhysX® are trademarks of NVIDIA Corporation. This project is not
affiliated with or endorsed by NVIDIA. Names within this namespace are used
solely as API compatibility identifiers per Google v. Oracle (2021).
"""

ADR = "ADR-2605261800"
PHASE = "R1.1-cartpole-poc"

NV_COMPAT_MAP = {
    "Omniverse Kit":   "amenominaka",
    "Nucleus":         "kotoba-datomic-nucleus",
    "Isaac Sim":       "e7m-sim",
    "Isaac Lab":       "e7m-shugyo",
    "OptiX":           "hikari-rt",
    "RTX Renderer":    "kami-rtx",
    "Replicator":      "utsushimi",
    "DriveSim":        "wadachi-sim",
    "Omniverse Cloud": "murakumo-render",
    "PhysX":           "kami-physx",
}
