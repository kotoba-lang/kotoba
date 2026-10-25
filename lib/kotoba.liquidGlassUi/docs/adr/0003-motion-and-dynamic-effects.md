# ADR 0003: overlay motion / spring press / pointer-tracking specular / SVG displacement lens

- **Status**: accepted — landed (2026-07-02), tests green (53 tests / 559 assertions)
- **Date**: 2026-07-02
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, motion, animation, svg, progressive-enhancement, cljc
- **Related**: `docs/adr/0001-liquid-glass-ui.md`, `docs/adr/0002-css-core-migration-and-ink-token.md`

## 背景

ADR 0001/0002 までで静的な glass material（blur/saturate/tint/elevation/
specular/rim/ink）は揃ったが、2 つの "Future work" 項目が未着手のまま残っていた:

- `liquid-glass__specular` span — "a future pointer-tracking enhancer or
  GPU/WebGPU refraction layer would target" とだけ書かれた予約 hook。
- 実際の refraction（背景を歪ませる真の屈折）は WebGPU 前提の
  `liquid-glass.gpu`（canvas context 専用）に先送りされていたが、DOM/CSS
  文脈（`kami-engine` の HUD 以外の、通常の web page）向けの選択肢が無かった。

加えて press/hover の motion は v1 から一貫して `cubic-bezier` 固定で、
Apple Liquid Glass 特有の「押すと少し撓んで、離すとわずかに弾む」ばね感が
無かった。overlay 系 component（sheet/alert/menu/tooltip/scrim）も出現/消滅の
transition を一切持っていなかった。

## Decision / 決定

4 層の **opt-in / progressive** motion & dynamic-effect レイヤーを追加した。
共通方針: 全ての duration/easing/offset/opacity は `--liquid-glass-*` token
（component-css は引き続き `css.core` の EDN data 経由）。全機能は pure CSS
か、JS 無しで静的 material に degrade する。`prefers-reduced-motion: reduce`
guard を `component-css` の **最後**のブロックとして emit し、同 specificity の
`@supports` upgrade 群より確実に後勝ちさせる。

### 1. Overlay enter/exit（`:liquid-glass/motion :overlay-enter` / `:overlay-exit`）

`scrim`/`sheet`/`alert`/`menu`/`tooltip` に `@keyframes` ベースの enter
transition（要素の **出現**＝挿入/初回 paint で走る。SSR で描かれた overlay や
`<details>` の open にも効く、mount hook 不要）。exit は「この library は
open/close state を持たない」という既存方針と整合させるため
**`[data-state="closing"]` 属性契約**にした: 呼び出し側が
`el.dataset.state = "closing"` をセット → `animationend` を待つ → 要素を
除去、という手順を呼び出し側が担う。`alert` の keyframes は中央寄せの
`translate(-50%,-50%)` を全フレームに畳み込んでいる（animation の transform は
rule の transform を**置き換える**ため）。

### 2. Spring settle + press morph（`:liquid-glass/motion :spring`, `:press :scale-x/:scale-y`）

CSS には native な spring timing function が無いため、
`liquid-glass.tokens/spring-linear-easing` という純粋関数で
under-damped spring の step response を解析的に計算し、CSS `linear(...)`
（区分線形イージング, Chrome 113+/Safari 17.2+/Firefox 112+）へ離散化した
（ζ=0.55, ω=13, 16 点サンプル。マジックリテラルではなく生成された値）。
`@supports (transition-timing-function: linear(0, 1))` で対応エンジンのみ
upgrade（button/icon-button の transform settle・toggle thumb・disclosure
chevron）。press morph は `:active` を一様 `scale(.97)` から
`scaleX(1.02) scaleY(.95)` の非対称 squash に変更 — 指先で押された glass が
歪む感覚。

### 3. Pointer-tracking specular highlight（library には含めない reference JS）

`liquid-glass__specular` span が予約していた hook を実装。ただし
**script 自体は library の export にしない**（"portable .cljc, zero deps" の
core 方針を壊すため）。代わりに `liquid-glass.style/specular-selector`
（public fn）が対象 host の CSS selector 一覧を生成し、
`liquid-glass.demo/specular-script`（`^:private`, ~70 行, dependency-free）が
GitHub Pages showcase 向けの reference 実装として存在する。consumer は
コピーするか、同じ contract（`--liquid-glass-pointer-x/-y` の書き込み、
`[data-lg-pointer]` の toggle、`<html>` への `.liquid-glass-js` 付与）で
自前の enhancer を書く。CSS 側は `.liquid-glass-js` が無ければ何も変わらない
（span は既定の `display:none` のまま）。`prefers-reduced-motion` は script
側（attach 自体を拒否）と CSS 側（guard で再度隠す）の二重防御。

script の実体は最初 `resources/liquid_glass/specular.js`（classpath resource）
だったが、`.cljc` へ将来昇格させる余地を残すため plain string 定数へ inline
した（`io/resource`+`slurp` は JVM 専用で cljs に持ち込めない）。

### 4. SVG displacement lens（`.liquid-glass--lens` + `lens-filter-defs`）

`backdrop-filter` の blur/saturate だけでは実現できない「背景を歪ませる」
refraction を、WebGPU を待たずに DOM/CSS だけで近似する。
`(lens-filter-defs)` が 0×0 の inline `<svg>`（`feTurbulence` →
`feDisplacementMap`, id `liquid-glass-lens`）をページに 1 回 emit し、
`:liquid-glass/lens {:frequency :scale :octaves}` token（SVG filter
primitive の属性は CSS custom property を読めないため、値は hiccup-emit 時に
解決）を feed する。`.liquid-glass--lens` class を付けた surface だけが
`@supports (backdrop-filter: url(#liquid-glass-lens))` 経由で
`url(#liquid-glass-lens)` を backdrop-filter chain に追加される —
**engine support は正直に限定的**（Chromium は compositing に制約付きで対応、
Safari/Firefox は `url()` を無視して素の blur にフォールバック）。
`@supports` は「url() をパースするが paint 時に無視する」ケースを検出できない
ため、upgrade 後の値も blur/saturate/brightness を保持したまま `url()` を
**追加**する構造にして、フォールバック時に backdrop 自体を失わないようにした。

### 付随修正: gauge の containing block

`gauge` は `glass-surface-components` に含まれない（`::before` は共有
specular ではなく内側 disc mask）ため base rule の `position:relative` を
受け取らない。`position:relative` 無しで絶対配置の `::before` を置くと
viewport 基準になり、ページ全体を覆う巨大な blur円として描画される実バグが
出た。`gauge-rules` 自身に `position:relative;isolation:isolate` を追加して
修正（`every-elevation-shadow-carries-both-rim-vars-test` 等のデータ駆動
test とは別の、レンダリング実測で見つかった不具合）。

### 付随修正: CI が `deps.edn` の `:local/root` shitsuke を解決できない

`deps.edn` の `:deps` 主エントリが（意図的に）`io.github.kotoba-lang/shitsuke
{:local/root "../shitsuke"}` になっているため、sibling checkout の無い CI
runner で `kbb -M:test` が解決失敗していた。`deps.edn` 側を書き戻す
（published git/sha に戻す）のではなく、**CI workflow 側に `git clone
--depth 1 https://github.com/kotoba-lang/shitsuke ../shitsuke` を追加**して
sibling を用意する形で解決した — ローカル開発と CI が同じ deps 解決経路
（shitsuke HEAD を直接参照）を通るようになる。

## Consequences

- **正向**: 静的な material から、実際に動く/反応する glass へ前進した。
  4 層とも「JS 無し」「reduced-motion で無効化」「@supports で正直に
  feature-detect」という同じ規律を共有しており、v1 の「zero deps, 常に
  static でも正しい」という契約を壊していない。
- **負向**: `component-css` の行数が大きく増えた（component-rules に
  overlay-motion-rules / specular-pointer-rules / lens-rules が追加、
  `@supports` upgrade block が 3 つに）。lens の実際の視覚効果は Chromium
  以外ではほぼ無い（正直に文書化済み）。
- **移行**: 既存 component の public API シグネチャは不変。`lens-filter-defs`
  が新規 export。overlay component（sheet/alert/menu/tooltip/scrim）を
  使う consumer は exit を使いたければ `[data-state="closing"]` 契約を
  自分で駆動する必要がある（付けなくても動作はする — 契約自体が opt-in）。

## Alternatives Considered

- **spring easing をベタ書きの `linear(...)` literal にする**: 却下。
  マジックナンバーの出所が追えなくなる。物理モデルから生成する方が
  retune も容易（`spring-linear-easing` の `ζ`/`ω`/`samples` を変えるだけ）。
- **pointer-tracking JS を library export にする**: 却下。zero-deps core の
  一貫性を壊す。CSS 契約だけを public にして JS は reference 実装に留める。
- **displacement lens を WebGPU 前提にして先送りし続ける**: 却下。DOM/CSS
  文脈で近似できる選択肢（SVG filter + `@supports` progressive enhancement）
  があるなら、GPU 実装を待つ理由が無い。真のクロスエンジン refraction は
  引き続き GPU path が担当（Future work に残置）。

## References

- `docs/design.md` § "Motion & dynamic effects"（4 層の詳細 + engine support）
- `docs/adr/0001-liquid-glass-ui.md`, `docs/adr/0002-css-core-migration-and-ink-token.md`
- `src/liquid_glass/tokens.cljk`（`spring-linear-easing`）
- `src/liquid_glass/style.cljk`（`overlay-motion-rules`/`specular-pointer-rules`/
  `lens-rules`/`spring-supports-css`/`lens-supports-css`）
- `src/liquid_glass/components.cljk`（`lens-filter-defs`）
- `src/liquid_glass/demo.cljk`（`specular-script` reference implementation）
