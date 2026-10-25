# ADR 0001: kotoba-ui — default UI/UX design single require point

- **Status**: accepted — scaffolded (2026-07-02)
- **Date**: 2026-07-02
- **Deciders**: Jun Kawasaki

## Addendum — `.kotoba` form-A string pipeline (2026-07-27)

Per ADR-2607270100 §10 / ADR-2607279200 Delivery #6, `kotoba/theme_core.kotoba`
ports the pure composition-layer string core (`hex->rgba`, accent decls,
layer-order, shell class/layout constants). Full `theme-css` still joins
shitsuke + liquid-glass + shell on the host `.cljc` side. Consumer APIs are
unchanged. Byte-equality is gated by `test/kotoba_ui/kotoba_parity_test.cljk`.
Oracle-backed experiment ahead of W4; not the final composition API.
- **Context tags**: ui, design-system, cljc, shitsuke, liquid-glass-ui
- **Related**: `90-docs/adr/2607022800-kotoba-lang-default-uiux-appkit-uikit-interface-fundamentals.md`
  (superproject decision), `90-docs/adr/2607011900-kotoba-lang-liquid-glass-ui.md`,
  `orgs/kotoba-lang/shitsuke`, `orgs/kotoba-lang/liquid-glass-ui`

## 背景

`shitsuke`（構造）+ `liquid-glass-ui`（マテリアル）は kotoba-lang の default
UI/UX design と位置づけられたが（superproject ADR-2607022800）、product repo が
default design 一式を得るには従来 `shitsuke.components` と
`liquid-glass.components` の両方を require する必要があった。単一 require
point が無かった。

`orgs/kotoba-lang/ui`（package `kotoba.ui`）という名前が近い repo が既に
存在するが、これは kami-engine の WebGPU HUD オーバーレイ描画専用（EDN spec →
DOM、ブラウザ CLJS 専用、CI green・テスト付き）であり、本 repo とは無関係。
名前の衝突を避けるため、この repo は `kotoba-ui`（`kotoba-ui.core`
namespace）とし、既存 `orgs/kotoba-lang/ui` は無変更のまま並存させる。

## 決定

`kotoba-ui` を新規 kotoba-lang repo として起こし、`kotoba-ui.core` を
shitsuke + liquid-glass-ui の**純粋な alias 層**として実装する。

- `kotoba-ui.core` は独自ロジック・独自 token・独自 CSS を一切持たない。
  全 var は `(def button liquid-glass.components/button)` の形の直接 alias。
- 対象は shitsuke.hiccup（`->html`）、liquid-glass.tokens（`resolve-tokens`
  等）、liquid-glass.style（`root-css`/`component-css`/`inline-style`）、
  liquid-glass.components（32 個の public component fn 全て）。
- テストは「alias 先と `identical?`」「単一 require で構造+マテリアルが
  両方乗った HTML が出る」の 2 点のみを検証する（新規ロジックが無いため）。

## なぜ shitsuke/liquid-glass-ui に統合せず別 repo にしたか

shitsuke は構造、liquid-glass-ui はマテリアルという明確な責務分離を持つ
（ADR-2607011900）。`kotoba-ui` はその 2 つを「product repo から見た時の
単一窓口」にするための合成層であり、どちらの責務にも属さない。将来 default
skin が liquid-glass-ui から別のものに変わっても、`kotoba-ui.core` の
require 先を差し替えるだけで product repo 側のコードは変わらない、という
間接層としての価値がある。

## Alternatives Considered

- **product repo が shitsuke + liquid-glass-ui を直接 require する**: 却下。
  今回は問題にならないが、default skin を将来差し替える際に全 product repo
  の require を書き換える必要が生じる。
- **既存 `orgs/kotoba-lang/ui` に kotoba-ui.core を追加する**: 却下。
  kami-engine HUD という既存の具体的 consumer と無関係な責務を同じ repo に
  混在させることになる。

## Consequences

- 正: product repo は `kotoba-ui.core` 一つを require すれば default design
  一式が手に入る。
- 負: alias 層が増えるぶん、shitsuke/liquid-glass-ui の破壊的変更が
  `kotoba-ui.core` にも波及する（ただし alias なので追従コストはほぼゼロ）。
- appkit/uikit repo の scaffold、7 プロダクトサイトへの実採用は follow-up
  （超project ADR-2607022800 の scope-boundary を参照）。
