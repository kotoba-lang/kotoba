# ADR 0001: appkit — desktop/dense-data platform binding

- **Status**: accepted — scaffolded (2026-07-02)
- **Date**: 2026-07-02
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, design-system, cljc, kotoba-ui
- **Related**: `90-docs/adr/2607022800-kotoba-lang-default-uiux-appkit-uikit-interface-fundamentals.md`
  (superproject decision), `orgs/kotoba-lang/kotoba-ui`, `orgs/kotoba-lang/uikit`

## 背景

superproject ADR-2607022800 は、Apple の UIKit/AppKit 分割になぞらえ、画面形状
ごとのデフォルト値を持つ二層バインディング（appkit/uikit）を `kotoba-ui` の上に
追加する方針を決めた。実装にあたり `liquid-glass.components` の実際の opts 契約
を確認したところ、`:surface`/`:elevation` を受け取るのは 32 コンポーネント中
`panel`（両方）と `list-view`（`:surface` のみ）の 2 つだけで、`toolbar`/
`nav-bar`/`sheet`/`alert` 等は固定の見た目を持ち、screen-shape ごとの差別化点が
存在しないことが分かった。

## 決定

`appkit.core` は `panel` と `list-view` のみをラップし、デスクトップ向けデフォルト
（`panel`: `:surface :thick` `:elevation :flat`、`list-view`: `:surface :thick`）
を `merge` で適用する。他の全コンポーネントは `kotoba-ui.core` から直接呼ぶ
（appkit は何もラップしない）。呼び出し側が opts を渡した場合は常にそちらが勝つ
（`merge default opts`）— liquid-glass-ui の他の wrap と同じ契約。

## Alternatives Considered

- **全 32 コンポーネントを appkit.core でラップする**: 却下。差別化点の無い
  コンポーネントをラップしても `(def x kotoba-ui.core/x)` の空 alias にしかならず、
  `kotoba-ui.core` を直接呼ぶのと何も変わらない。無意味な間接層を増やすだけ。
- **`toolbar`/`nav-bar` 等に独自の `:density` opt を追加する**: 却下（本 repo の
  スコープ外）。liquid-glass-ui 自体への opt 追加は liquid-glass-ui 側の変更であり、
  appkit が肩代わりすべきではない。将来 density variant が必要になった時点で
  liquid-glass-ui 側に follow-up ADR を立てる。

## Consequences

- 正: 実在する差別化点のみをラップしたことで、appkit のコードと README が
  「なぜこの2つだけか」を正直に説明できる。
- 負: `panel`/`list-view` 以外のコンポーネントは appkit を経由しても screen-shape
  ごとの見た目の違いが一切無い。dense-table 系の新規コンポーネントが将来
  liquid-glass-ui に追加された際、appkit 側にも対応するデフォルトを追加する
  follow-up が必要。
