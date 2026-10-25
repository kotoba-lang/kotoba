# ADR 0001: shitsuke — kotoba-lang shared UI design system

- **Status**: accepted — landed (2026-06-30), tests green
- **Date**: 2026-06-30
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, design-system, cljs, reframe, shadowcss, hiccup, portable
- **Related**: `90-docs/adr/<ts>-shitsuke-design-system.md` (superproject),
  `orgs/kotoba-lang/slides`, `orgs/kotoba-lang/kami-engine/kami-mangaka-reader-clj`,
  `orgs/kotoba-lang/wasm-ui`, `orgs/kotoba-lang/office-style`

## Addendum — `.kotoba` form-A string pipeline (2026-07-27)

Per ADR-2607270100 §10 / ADR-2607279200 Delivery #6, `kotoba/tokens_core.kotoba`
and `kotoba/hig_core.kotoba` port the pure token → CSS-string pipeline
(`--shitsuke-*` / `--hig-*` emission, layer-order, text-style-props). Dual-render
seams (reagent/re-frame) stay on the host `.cljc` side. Consumer APIs are
unchanged. Byte-equality is gated by `test/shitsuke/kotoba_parity_test.cljk`.
This is an oracle-backed experiment ahead of W4; not the final design-system API.

## 背景

`kotoba-lang` 配下のフロントエント系 repo は each ごとに UI 層を自前で書いており、
共通 design system が無い:

- `slides` — 自作 `slides.hiccup`（JVM 専用）+ `slides.web.cljs` が生 atom + innerHTML
  文字列書き + 巨大 click `cond`。shadow-css は shell 3 クラス分のみ。token
  (`slides.design`) は PPTX/DrawingML geometry 向きで CSS 向きでない。
- `kami-mangaka-reader-clj` — 一番きれいな dual-render 参考実装（`.cljc` 純 hiccup →
  SSR + reagent/re-frame）。ただし CSS は手書き文字列で token→CSS emitter 無し。
- `wasm-ui` — WASM 向けミニ re-frame（7 関数）+ `re-frame.core`/`reagent.core` compat
  namespace。effect/cofx/interceptor/chaining は意図的に持たない。
- `slides.hiccup` と `kami.mangaka.hiccup` はほぼ同一の依存ゼロ hiccup→HTML renderer の重複。

token・hiccup・style・state のどれも共通化されていない。

## 決定

`shitsuke`（仕付け）を新規 kotoba-lang repo として起こし、以下 4 層 + component を
ポータブル `.cljc` ライブラリとして束ねる。core は第三者 runtime dep ゼロ（dot/kasane
と同形）。real reagent/re-frame/shadow-css は `:cljs`/`:pages` alias の extra-deps。

### 層

| 層 | 役割 |
|---|---|
| `shitsuke.tokens` | design token IR + `deep-merge` resolver + `css-variables`（`:root` CSS vars）+ `from-slides-design` adapter |
| `shitsuke.hiccup` | 依存ゼロ hiccup→HTML renderer（`->html`/`esc`/void-tags/`:hiccup/raw`）。`kami.mangaka.hiccup` と `slides.hiccup` を統合 |
| `shitsuke.style` | token→CSS `:root` vars（portable）+ `shitsuke__*` class-name registry |
| `shitsuke.re-frame` | ミニ re-frame runtime（7 関数: `app-db`/`clear!`/`reg-event-db`/`reg-sub`/`dispatch`/`dispatch-sync`/`subscribe`）。wasm-ui 由来 |
| `shitsuke.re-frame.core` | host seam。`:cljs` → real re-frame 1.4.3、`:clj` → ミニ runtime。アプリコードは `[shitsuke.re-frame.core :as rf]` で host 非依存 |
| `shitsuke.reagent.core` | host seam。`:cljs` → real reagent 1.2.0、`:clj` → `hiccup/->html` |
| `shitsuke.components` | 純 hiccup UI primitives（reagent import しない） |

### 契約

- **dual-render**: 同じ `.cljc` 純 hiccup view を SSR（`->html`）と reagent（cljs）の両方へ
  （mangaka reader と同契約）。view は reagent import しない。
- **portable re-frame subset**: アプリコードは 7 関数のみを使い、effect/cofx/interceptor/
  subscription chaining(`<-`) を使わない（wasm-ui `compat_api_test` が pin する subset）。
- **style 2 段**: (a) token→CSS custom properties（`:root` vars, portable, SSR 向け）
  + (b) `com.thheller/shadow-css` による scoped class CSS（build 時, consumer が
  `:pages` build の `:include` に `shitsuke.components` を追加）。
- **class 命名**: `shitsuke__<component>`（`shitsuke.style/class-name`）。view の `:class`
  と shadow-css 抽出 anchor の両方で使う安定名。

### 最初の利用者

`slides` を最初の利用者として移行する（別 ADR / 別 commit で追跡）。`slides.web.cljs`
（生 atom + innerHTML + 巨大 cond）を `views.cljc`（純 hiccup）+ `app.cljs`（re-frame
mount）+ `ssr` へ分割し、design token は `shitsuke.tokens/from-slides-design` で CSS var 化、
editor クラスを `shitsuke.components` + shadow-css `:include` 拡張へ。

## Consequences

- positively: token/hiccup/style/state の単一 SSoT。新しい frontend repo（kobo/freeboard/
  wasm-ui/mangaka-reader）は shitsuke を require するだけで UI 層が揃う。重複 hiccup
  renderer の統合。
- negatively: 既存 `slides.hiccup`/`kami.mangaka.hiccup` の呼び出し元を shitsuke.hiccup へ
  切替える follow-up が必要（slides 以外は段階移行）。
- アプリコードが portable subset（7 関数）を超える re-frame 機能を使うと JVM SSR で動かない。
  lint/test で subset を pin し続ける。

## Alternatives Considered

- **既存 repo（slides 等）に token/hiccup 層を置く**: 却下。複数 frontend repo で共有できず
  重複が続く。kotoba-lang は関心事単位の short-Japanese-word repo 慣例（kuro/kobo/koe/...）。
- **real re-frame のみ（ミニ runtime 無し）**: 却下。JVM SSR / babashka / WASM host で
  real re-frame が動かない。wasm-ui の compat-namespace パターンが実績済み。
- **shadow-css のみ（token→CSS var emitter 無し）**: 却下。SSR (babashka) で shadow-css
  build が使えず、token から `:root` vars を出せない。2 段構成で両立。

## References

- `90-docs/adr/2606282101-mangaka-multilingual-text-layer-cljc-hiccup-reader.md`
  (dual-render 参考実装)
- `90-docs/adr/2606301000-kotoba-kobo-kuro-terminal-editor.md` (scaffold 慣例)
- `orgs/kotoba-lang/wasm-ui/src/kotoba/wasm/re_frame.cljc` (ミニ runtime 由来)
- `orgs/kotoba-lang/kami-engine/kami-mangaka-text-clj/src/kami/mangaka/hiccup.cljc`
  (hiccup renderer 由来)
