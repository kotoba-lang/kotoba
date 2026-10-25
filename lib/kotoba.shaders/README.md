# kotoba-lang/shaders

The production lit shader uses an ACES filmic fit before output gamma, giving
sun and emissive highlights a controlled roll-off while retaining colour.

**SSoT** for `kami.shaders` (ADR-2607102200 addendum 5). Extracted from webgpu vendor copy.

| Namespace | Role |
|---|---|
| `kami.shaders` | Implementation |
| `kotoba.shaders` | Compatibility facade |

`webgpu` depends on this package; do not re-vendor.
