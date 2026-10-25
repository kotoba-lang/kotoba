# kotoba-lang/scene2d

**SSoT** for `kami.scene2d` + `kami.text` (GPU 7-segment) — ADR-2607102200 addendum 5.

| Namespace | Role |
|---|---|
| `kami.scene2d` | 2D frame assembly → GPU quads |
| `kami.text` | 7-segment glyph → quads (not `kotoba-lang/text` string utils!) |
| `kotoba.scene2d` | Compatibility facade |

Depends on `sprite-gpu` + `sprite2d`. Extracted from webgpu vendor copy.
