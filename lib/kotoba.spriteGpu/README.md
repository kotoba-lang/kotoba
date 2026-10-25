# kotoba-lang/sprite-gpu

**SSoT** for GPU-instanced 2D sprite quads (ADR-2607102200 addendum 5).

| Namespace | Role |
|---|---|
| `kami.sprite-gpu` | Implementation (rect half-extents fix included) |
| `kotoba.sprite-gpu` | Compatibility facade |

Was previously vendored inside `webgpu`; that copy is removed — depend here.
