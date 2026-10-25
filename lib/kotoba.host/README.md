# kotoba-lang/host

**Browser game host surface** (ADR-2607102200 addendum 8):

| ns | role |
|---|---|
| `kami.host` | WASM/ECS import object for compiled kami games |
| `kami.input` | keyboard/gamepad → axes |
| `kami.ui` | DOM HUD widgets |
| `kami.audio` | Web Audio synth bank |
| `kotoba.host` | thin facade over `kami.host` |

Depends on `physics` for collision. Does **not** depend on `webgpu`.

## Test

```sh
kbb -M:test
```
