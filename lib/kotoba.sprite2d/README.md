# kotoba-lang/sprite2d

**SSoT for 2D sprites:**

| ns | role |
|---|---|
| `kami.sprite2d.layout` | pure draw-list (camera, depth, variants) — `.cljc` |
| `kami.sprite2d` | Canvas2D painter — `.cljs` |
| `kotoba.sprite2d*` | thin facades |

See ADR-2607102200 addenda 5 + 7.

## Test

```sh
kbb -M:test
```
