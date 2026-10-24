# css agent rules

- ADR-0001のshadow-css-compatible static CSS contractを正本とする。
- `(kotoba.css.shadow/css ...)` は静的form、source由来class、build-time抽出、zero runtime生成を守る。
- serializer、source index、validation、minify、write、utility aliasはapp repoへ複製しない。
- portable EDN sheetとnative material tokenはadditive extensionとし、web class semanticsを変えない。
- 未対応utilityや不正sheetはstrict buildでfail closedにする。
- 出力はdeterministicにし、生成物を手編集しない。
