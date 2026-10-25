# kotoba-lang/pipelines

**SSoT for `kami.pipelines`** — open-world render pipeline specs as EDN (`.cljc`).

Includes `parse-rust` for optional drift-gating against legacy native `scene_pipelines.rs`.

`kotoba.pipelines` is a thin facade. See ADR-2607102200 addendum 7.

## Test

```sh
kbb -M:test
```
