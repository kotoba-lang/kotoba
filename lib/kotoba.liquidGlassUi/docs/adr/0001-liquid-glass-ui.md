# ADR 0001: liquid-glass-ui — kotoba-lang shared "liquid glass" visual skin on shitsuke

- **Status**: accepted — landed (2026-07-01), tests green
- **Date**: 2026-07-01
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, design-system, glassmorphism, cljc, shitsuke
- **Related**: `90-docs/adr/2607011900-kotoba-lang-liquid-glass-ui.md` (superproject),
  `90-docs/adr/2606301900-kotoba-lang-shitsuke-design-system.md`,
  `orgs/kotoba-lang/shitsuke`, `orgs/kotoba-lang/ui`, `orgs/kotoba-lang/webgpu`

## Addendum — `.kotoba` form-A string pipeline (2026-07-27)

Per ADR-2607270100 §10 / ADR-2607279200 Delivery #6, `kotoba/tokens_core.kotoba`
ports the pure token → CSS custom-property pipeline (light + dark). Component
hiccup and `style.cljc` EDN→css.core rules stay on the host `.cljc` side.
Consumer APIs are unchanged. Byte-equality is gated by
`test/liquid_glass/kotoba_parity_test.cljk`. Oracle-backed experiment ahead of
W4; not the final material API.

## 背景

`shitsuke` は kotoba-lang 共通 UI design system（token IR + hiccup renderer +
CSS-var style 層 + portable re-frame + 純 hiccup component primitives）だが、
意図的に**視覚（見た目）に無関心**（class 名 hook のみ提供、inline visual CSS は
持たない）。一方で kotoba-lang 配下の複数 frontend 候補（`slides`, `wasm-ui`,
`kobo`/`kuro` editor, `kami-engine` の `kotoba.ui` HUD 等）は、それぞれ独自に
半透明/blur 系の見た目を書くか、見た目を持たないままになっている。Apple の
"Liquid Glass"（iOS 26 系デザイン言語: 半透明 + blur/saturate + specular
highlight + 背景追従の tint）に相当する共通ビジュアルスキンが無い。

## 決定

`liquid-glass-ui` を新規 kotoba-lang repo として起こし、**shitsuke の上に乗る
視覚スキン専用ライブラリ**として設計する。shitsuke 同様 portable `.cljc`、
runtime dep は shitsuke のみ。

### 層

| 層 | 役割 |
|---|---|
| `liquid-glass.tokens` | material token IR（`:liquid-glass/surface` `:elevation` `:specular` `:radius` `:motion`）+ light/dark resolver（`prefers-color-scheme: dark` で同名 CSS var を上書きする方式） |
| `liquid-glass.style` | `class-name` registry（`liquid-glass__<component>`）+ Tier A `root-css`（CSS vars）+ Tier B `component-css`（backdrop-filter/specular/elevation/motion の実 CSS。shadow-css ビルド不要のポータブル文字列） |
| `liquid-glass.components` | 純 hiccup: `panel`/`button`/`icon-button`/`toolbar`/`tab-bar`/`sheet`/`scrim`/`badge`。button/icon-button/toolbar/panel は `shitsuke.components` を wrap（act 契約そのまま）、sheet/scrim/badge は shitsuke に対応物が無いため直接実装 |

### なぜ shitsuke に統合せず別 repo にしたか

`shitsuke` の役割は「構造（token/hiccup/state/class 名 hook）」であり、
「特定の見た目」を持ち込むと、見た目を必要としない/別の見た目を選びたい
consumer（将来のフラット skin 等）が glass 固有 token/CSS を巻き込まれる。
関心事分離のため別 repo とし、shitsuke への依存は deps.edn の通常の git dep
（`chobo`/`mise`/`senden` と同形）。

### shitsuke 自身の shadow-css 統合が未完である点への対応

shitsuke ADR（2606301900）の "負向" にある通り、`shitsuke.components` の
実 CSS は shadow-css `:pages` build 経由という設計だが**まだ配線されていない**
（class 名 hook のみ存在）。liquid-glass-ui は同じ罠を踏まないため、Tier B
（`component-css`）を **shadow-css マクロに依存しないポータブル literal CSS
文字列**として実装した。ビルドステップ無しで SSR にも browser にも同じ文字列を
埋め込める。shadow-css 抽出は shitsuke 側の配線が済んでから検討する
follow-up（`docs/design.md` #future-work）。

## Consequences

- **正向**: kotoba-lang 配下の frontend repo（slides / wasm-ui / kobo / freeboard
  等）は `liquid-glass.components` を require するだけで Apple Liquid Glass 系の
  見た目が手に入る。material は token 差し替えのみで再テーマ可能（inline CSS を
  持たないため）。
- **負向**: v1 は DOM（CSS backdrop-filter）限定。canvas/WebGPU コンテキスト
  （`kami-engine` の `kotoba.ui` HUD 等）向けの真の refraction/squircle 描画は
  無い（`liquid-glass.gpu` は follow-up、`docs/design.md` に明記）。
- **移行**: 各 frontend repo での採用は個別 follow-up（本 ADR はライブラリ自体の
  設計・scaffold のみを完了条件とする）。

## Alternatives Considered

- **shitsuke に glass 見た目を直接追加**: 却下。関心事分離が壊れ、別の見た目を
  選びたい consumer が glass token/CSS を巻き込まれる。
- **CSS-in-JS / 独自ビルドツール導入**: 却下。kotoba-lang の portable `.cljc`
  + zero-third-party-runtime-dep 慣例（`dot`/`kasane`/`shitsuke` と同形）と
  合わない。ポータブル文字列生成で十分。
- **v1 から WebGPU 実 refraction を実装**: 却下（過剰実装）。具体的な
  canvas コンテキスト consumer が現れてから `liquid-glass.gpu` として追加する。

## References

- `90-docs/adr/2606301900-kotoba-lang-shitsuke-design-system.md`
- `orgs/kotoba-lang/shitsuke/docs/design.md`
- `docs/design.md`（本 repo の層別 API）
