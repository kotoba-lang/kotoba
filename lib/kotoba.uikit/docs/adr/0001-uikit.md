# ADR 0001: uikit — touch/mobile/card-first platform binding

- **Status**: accepted — scaffolded (2026-07-02)
- **Date**: 2026-07-02
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, design-system, cljc, kotoba-ui
- **Related**: `90-docs/adr/2607022800-kotoba-lang-default-uiux-appkit-uikit-interface-fundamentals.md`
  (superproject decision), `orgs/kotoba-lang/kotoba-ui`, `orgs/kotoba-lang/appkit`

## 背景

`appkit`（ADR-0001-appkit）と対になる、touch/mobile/card-first 向けの platform
binding。`liquid-glass.components` の実際の opts 契約を確認した結果は appkit と
共通で、`:surface`/`:elevation` を受け取るのは `panel`/`list-view` のみ。

## 決定

`uikit.core` は `panel`（`{:surface :clear :elevation :floating}`）と
`list-view`（`{:surface :regular}` — component 自身のデフォルトと同値、
明示するだけの no-op）のみをラップする。他の全コンポーネントは
`kotoba-ui.core` から直接呼ぶ。呼び出し側の opts は常に勝つ。

`list-view` のデフォルトを component 自身のデフォルトと同じ `:regular` に
した理由: モバイルのカードリストは thick surface による強調を必要としない
（appkit のダッシュボード的密度と違い、単一カラムでコンテンツ自体が主役）。
無意味に見えるが「意図的に何もしない」ことの記録として残す。

## Alternatives Considered

appkit の ADR-0001 と同一の理由で、全コンポーネントラップ・独自 opt 追加は
却下。

## Consequences

- 正: appkit と対称的な構造で、両 repo の README/design.md を同じ表形式で
  比較できる。
- 負: `list-view` のデフォルトが実質 no-op であるため、コードだけを見ると
  「なぜここに存在するのか」が分かりにくい — README/design.md のコメントで
  補う。
