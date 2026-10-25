# ADR 0002: component-css を kotoba-lang/css の EDN データ生成へ移行 + :liquid-glass/ink token 追加

- **Status**: accepted — landed (2026-07-02), tests green (42 tests / 417 assertions)
- **Date**: 2026-07-02
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, css, design-system, quality, cljc
- **Related**: `docs/adr/0001-liquid-glass-ui.md`, `orgs/kotoba-lang/css`,
  `orgs/kotoba-lang/html`, `orgs/kotoba-lang/shitsuke`

## 背景

v1（ADR 0001）の `liquid-glass.style/component-css` は約 350 行の手書き CSS
文字列連結だった。この設計で実際に 2 件のバグを踏んだ：

1. `:elevation :flat` panel が `liquid-glass__panel--flat` class を正しく
   emit するのに、対応する CSS ルールを書き忘れていた（class はあるのに
   効果ゼロ）。
2. `:liquid-glass/specular :rim`（edge の top/bottom opacity）token を token IR
   には定義したのに、どの CSS ルールからも一度も参照していなかった
   （token はあるのに配線されていない = orphaned token）。

どちらも「文字列を書き忘れる」という同じ形の欠陥で、文字列連結ではコンパイラも
lint も検出できない。一方 `kotoba-lang/css`（`css.core`, "CSS as EDN data"）
と `kotoba-lang/html`（"the standalone substrate form of the renderer that
previously lived in shitsuke.hiccup"）という 2 つの kotoba-lang 基盤 repo が
既に存在し、どちらも consumer が 0 件のまま公開されていた。

## Decision / 決定

### 1. component-css を css.core の EDN rule data から生成する

`liquid-glass.style` に `io.github.kotoba-lang/css` を runtime dep として追加。
`component-css`（文字列）はそのまま public API として残しつつ、内部を
`component-rules`（`[selector decls-map]` の vector, public）→
`css.core/css` render という2段に分離した。

- 4 つの private 宣言マップ helper（`backdrop-decls`/`glass-bg-decls`/
  `glass-shadow-decls`/`ink-decls`、後述）が返す Clojure map を各 `-rules`
  関数が `merge` して組み立てる。手書き文字列コピペではなく、同じ helper
  呼び出しなので「blur だけ書いて brightness を忘れる」「shadow だけ書いて
  rim を忘れる」が構造的に起きにくい。
- `@supports`（css.core が対応しない at-rule）だけは手書き文字列で残すが、
  内側の宣言は `css.core/rule` を通す。
- `component-rules` を public にしたことで、test が **rendered string の
  regex scrape ではなく data を直接 assert** できるようになった。実例:
  `every-elevation-shadow-carries-both-rim-vars-test` は
  `component-rules` を走査し、`:box-shadow` に `elevation` shadow が含まれる
  のに rim var が無ければ fail する。この test 自体が実際に 1 件のバグを
  検出した — `slider` の vendor-prefix thumb pseudo-element
  （`::-webkit-slider-thumb`/`::-moz-range-thumb`）が `glass-shadow-decls`
  helper を経由せず手書きされていて rim を欠いていた。修正して helper 経由に
  揃えた。

`kotoba-lang/html` は採用しない。README が明言する通り、これは
`shitsuke.hiccup` の standalone 抽出であり、liquid-glass-ui が既に依存する
shitsuke の dual-render 契約（SSR ‖ reagent）と機能的に重複する。shitsuke
自身がまだ `kotoba-lang/html` に移行していない以上、liquid-glass-ui が
第三の renderer 依存を追加する理由は無い。

### 2. `:liquid-glass/ink` token を追加し、text legibility をライブラリ側に持つ

v1 は base rule で `color:inherit` としていたため、consumer 側の任意の
祖先 color をそのまま継承していた。GitHub Pages showcase（`docs/index.html`）
を作る過程で、カラフルな gradient 背景の上で読める文字色をデモ側の CSS に
手書きするまで気付かなかった — つまり consumer 側で毎回同じ workaround を
複製しないと glass 上のテキストが読めない、というライブラリ側の欠落だった。

`:liquid-glass/ink {:default ... :shadow ...}` を追加。light scheme は暗い
ink（`#1c1c1e`）+ 明るい shadow、dark scheme（`dark-tokens` override）は
明るい ink（`#f5f5f7`）+ 暗い shadow — `:surface` tint と同じ
`prefers-color-scheme` 再宣言方式。`ink-components`（`glass-surface-components`
のスーパーセット、toggle/checkbox/radio の外側 `<label>` 等テキストを持ち得る
全 top-level component root）に対して `color`/`text-shadow` を 1 箇所で設定 —
どちらも inherited property なので nested span（checkbox-text 等）へは
サブエレメント毎のルール無しで伝播する。

**やらないこと**: 背景の実際の輝度をサンプリングした adaptive tinting
（Apple 実装が持つ「背景色に応じて自動で white/black を選ぶ」）。これは
JS か GPU compositing が要る（ADR 0001 の "Future work" 記載どおり
`liquid-glass.gpu` follow-up の範疇）。`ink` は OS の `prefers-color-scheme`
にのみ追従する。個々の consumer の背景と衝突する場合（本 repo 自身の
`docs/index.html` がカラフルな gradient に対して常に白文字を選んでいるように）
は consumer 側で `color`/`text-shadow` を上書きする — これは他の CSS
デフォルトの上書きと同じ扱いであり、ライブラリが「基本は読める」状態を
保証した上での話になる。

## Consequences

- **正向**: バグの再発防止（token/class を書いてルールを忘れる、をデータレベルで
  test できる）。テキストの可読性がライブラリの責務になり、consumer 側の
  重複 workaround が不要になった。`kotoba-lang/css` の実利用第一号になり、
  同 repo の設計を実地検証した。
- **負向**: runtime dep が 1 つ増えた（shitsuke, css の 2 依存）。`:local`
  alias は `../shitsuke` と `../css` の両方が sibling に必要。
- **移行**: 既存の public API（`component-css`, `root-css`, `class-name`,
  `inline-style*`）はシグネチャ不変。`component-rules` が新規追加のみ。
  破壊的変更なし。

## Alternatives Considered

- **css.core を使わず手書き文字列のまま、テストだけ強化する**: 却下。
  テストを強化しても「書き忘れ」の発生源（文字列コピペ）は残る。データに
  すること自体が発生源を減らす。
- **kotoba-lang/html も同時に採用**: 却下。shitsuke の dual-render 契約と
  機能重複するだけで、liquid-glass-ui にとって追加の価値が無い。
- **ink を color のみにして text-shadow を省く**: 却下。単色の再宣言だけでは
  busy な（写真・グラデーション）背景での可読性が不十分。soft shadow は
  実質コストゼロ（inherited property 1 個追加）で効果がある。

## References

- `docs/adr/0001-liquid-glass-ui.md`
- `orgs/kotoba-lang/css/src/css/core.cljc`
- `docs/design.md`（layer 別 API、text legibility の詳細説明）
