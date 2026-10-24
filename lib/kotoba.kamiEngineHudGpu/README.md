> **Note (ADR-2607102200 addendum 2):** sibling `kami-engine-hud` (`kotoba.ui`)
> is merged into `kami-engine-app-sdk`. This GPU backend package is unchanged.

# kotoba-lang/kami-engine-hud-gpu

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-ui-gpu` Rust crate
(`src/lib.rs`, 354 lines; deleted in `kotoba-lang/kami-engine` PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`). GPU rendering backend for
[`kami-engine-hud`](https://github.com/kotoba-lang/kami-engine-hud) (`kotoba.ui`),
renamed from `kotoba-lang/ui-gpu` to avoid collision with the `kotoba-ui`/`appkit`/
`uikit` app design-system family, which is an unrelated stack (see
`90-docs/adr/2607051200-kotoba-lang-ui-family-rename.md` in `com-junkawasaki/root`).

## Status

Restored. `src/ui_gpu.cljk` ports every public struct/enum/fn from the original crate as
pure data (plain maps with keyword keys) + pure functions:

- `UiRect` / `UiText` / `UiColorGlyph` GPU instance shapes (`ui-rect`, `ui-text`,
  `ui-color-glyph`)
- `GradientDir` enum -> `gradient-dir-values` set
- `UiCommand` enum -> tagged command maps (`:rect` / `:text` / `:color-glyph` /
  `:circle` / `:gradient`)
- `UiLayer` command batcher (`ui-layer`, `rect`, `rounded-rect`, `bordered-rect`,
  `circle`, `text`, `color-glyph`) and its flattening functions (`to-instances`,
  `to-text-instances`, `to-color-glyph-instances`, `circle->rect`)
- `ToastLevel` enum -> `toast-level-values` set + `toast-level-color`
- `Toast` / `ToastStack` notification-queue primitive (`toast-stack`,
  `toast-stack-push`, `toast-stack-tick`, `toast-stack-render`)

There is no literal wgpu pipeline/shader/device code in the original file — it is a
pure instance-buffer-layout and command-batching module, so everything ported is
portable computational/data-shape logic. Native GPU submission (wgpu / wasmtime /
wasmi) stays substrate and is out of scope for this namespace.

All 3 original Rust `#[test]`s (`test_toast_stack`, `test_toast_level_colors`,
`test_ui_layer`) are ported 1:1 to `test/ui_gpu_test.cljk`, plus the `namespace-loads`
smoke test and one additional test covering `bordered-rect` and gradient-command
flattening. **5 tests / 14 assertions, 0 failures, 0 errors.**

## Develop

```bash
kbb -M:test
```
