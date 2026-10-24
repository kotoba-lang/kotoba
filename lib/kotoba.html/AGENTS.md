# html agent rules

- ADR-0001のHiccup-compatible contractを正本とする。
- valid Hiccup element、fragment、seq child、class/style/boolean attrs、void tagの意味を変えない。
- textとattributeは既定でescapeし、raw markupは明示的なtrusted wrapperだけに限定する。
- HTML文字列をnative UIの中間表現にしない。portable Hiccup treeを共有契約とする。
- app固有rendererへHiccup normalizationを複製しない。
- `html.core` は消費者向け API のまま維持する。`.kotoba` 移植（`kotoba/html_core.kotoba`）は
  facade の裏に置く form A 実験で、parity gate（`test/html/kotoba_parity_test.cljk`）を壊さない。
  最終 API 化は ADR-2607279200 W4 後。compiler は test-only 依存。
