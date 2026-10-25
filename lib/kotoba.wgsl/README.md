# kotoba-lang/wgsl

**SSoT for WGSL-as-data** (hiccup → WGSL string). ADR-2607102200.

| Namespace | Role |
|---|---|
| `kami.wgsl` | Implementation (shared with `webgpu` and friends) |
| `kotoba.wgsl` | Compatibility facade re-exporting `kami.wgsl` |

Depends only on `expr` (shared infix core). No browser/WebGPU deps.

```sh
kbb -M:test
```
