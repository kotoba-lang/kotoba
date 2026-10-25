# 実装状況 (STATUS)

`office-style` の機能と検証状況。最終更新: 2026-07-03。

**注記**: このドキュメントは元々、`office-style.runtime` を CLJC へリファクタする前の
TypeScript 実装(`src/types.ts` の zod スキーマ、`toSvgraphPresentation`/
`toSvgraphIngest`、Gemma vision、WebGPU 等)を記述していた。`0c7e434`
(Refactor office-style runtime to CLJC) 以降、実装は `src-cljc/office_style/`
配下の4ファイル(`opc.cljc`/`style.cljc`/`preview.cljc`/`svgraph.cljc`、
合計 約200行)に縮小されており、旧ドキュメントが記述する機能の大半
(clrMap/clrMapOvr 解決、placeholder 継承、custGeom、グラデーション、
表・画像描画、guides、textStyles、tone/vision 解析)は**現行実装には
存在しない**。本更新はこの乖離を是正し、現状を正直に記録する。
`docs/ir-schema.md` および `docs/adr/000{1,2,3,4}-*.md` は旧
TypeScript 実装時代の設計文書であり、現行 CLJC 実装のスキーマとは
一致しない(参照時は要注意)。

## 現行実装の機能マトリクス (`src-cljc/office_style/`)

| ファイル | 機能 | 状態 |
|---|---|---|
| `opc.cljc` | pptx zip から `.xml`/`.rels` パートのみ読み込み(JVM専用、cljsは例外) | ✅ |
| `style.cljc` | theme の生 `srgbClr`/`sysClr lastClr` 色抽出(schemeClr解決・clrMap適用は無し) | ✅ |
| | theme フォント (major/minor の latin/ea/cs) 抽出 | ✅ |
| | `<p:sldSz>` からのスライドサイズ抽出 | ✅ |
| | slide/layout/master の**パート名一覧**(自然数順ソート済み、中身は未パース) | ✅ |
| | XML数値/名前実体デコード、単一/二重引用符属性、pretty-print XML耐性 | ✅ |
| | 不正/欠損パッケージへのフォールバック(空色/空フォント/nilサイズ/0サイズ) | ✅ |
| `preview.cljc` | StyleIR からの固定レイアウトSVGプレビューカード(実スライド描画ではない) | ✅ |
| `svgraph.cljc` | StyleIR → svgraph向けEDN投影(masters/layouts/slidesは `{id part}` のみ、shapesは常に空配列) | ✅ |

## 現行実装に存在しない旧仕様(旧STATUS.mdの記載、要再実装確認)

以下は全て**現行 `.cljc` 実装には無い**(schemeClr解決の基盤自体が未実装のため、
`phClr` 解決も含めここからの再実装が前提になる):

- `clrMap`/`clrMapOvr` 二段解決、`phClr` の文脈依存解決
- slideMaster/slideLayout の中身(背景・placeholder・txStyles・type・master リンク)の構造化パース
- guides 抽出
- レンダラ(prstGeom/custGeom/塗り/回転/表/画像枠の実描画)
- placeholder スタイル継承
- vision (Gemma multimodal, WebGPU) 一式
- `toSvgraphPresentation`/`toSvgraphIngest` という名前の関数(現行は `svgraph/presentation` のみ)

## 検証

| スイート | コマンド | 結果 |
|---|---|---|
| ユニット (`office-style.style`/`.preview`/`.svgraph`/`.cli` の17 deftest) | `kbb -X:test`(`npm test` 経由) | pass |

旧STATUS.mdが記載していた `verify:svgraph`/`verify:real`/vision実機/型チェック等の
検証コマンド群は、対応する実装(旧TS runtime)自体が現行コードベースに存在しないため
今は実行できない。

## 今後

現行の薄い CLJC 実装を、実際の README が謳う範囲(theme色/フォント/スライドサイズ/
パート一覧の決定論抽出、プレビューSVG、svgraph投影)に対して着実に固めるのが最優先。
schemeClr解決・clrMap・placeholder継承・実レンダリングを追加するかどうかは、
どのスコープまで `office-style` に持たせるか(vs. 上流の drawingml/presentationml/slides
が既に持つ同等機能との重複)を判断してから着手する。
