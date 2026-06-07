# kotodama.nv_compat

**Drop-in NVIDIA Omniverse stack API-compat facade** for `kotodama`.

**Status**: R1.0 path reservation (ADR-2605261800).

## Purpose

This namespace exposes the public, documented Python API surface of NVIDIA
Omniverse stack so existing scripts can be ported with **import-path-only
changes** to run on KAMI + WebGPU + WASM via Pyodide or native MicroPython.

## Drop-in example

```python
# original (Omniverse)
import omni.usd
import omni.replicator.core as rep
from isaacsim.core.api import World
from isaaclab.envs import ManagerBasedRLEnv

# nv-compat version (only import paths change)
import kotodama.nv_compat.omni.usd as omni_usd
import kotodama.nv_compat.omni.replicator.core as rep
from kotodama.nv_compat.isaacsim.core.api import World
from kotodama.nv_compat.isaaclab.envs import ManagerBasedRLEnv
```

## Trademark notice

NVIDIA®, Omniverse®, Isaac®, OptiX®, RTX®, Nucleus®, DriveSim® are trademarks
of NVIDIA Corporation. This project is not affiliated with or endorsed by NVIDIA.
The NVIDIA names appearing within this namespace are used solely as **API
compatibility identifiers** (per Google v. Oracle, 593 U.S. ___ (2021)).

## Scope (intentionally limited)

- ✅ Public, documented Python API surface
- ❌ Private / undocumented / internal `omni.*` modules
- ❌ Binary SDK linking, header copy, asset bundle redistribution

## License

Apache 2.0 + Charter Compliance Rider v2.0 (`/CHARTER-RIDER.md`).
