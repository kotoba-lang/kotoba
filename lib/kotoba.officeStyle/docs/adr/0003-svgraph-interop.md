# ADR 0003: svgraph との相互運用 (2 つの出力シェイプ)

- Status: Accepted
- Date: 2026-06-24
- 関連: 0001 (StyleIR), svgraph `SVGraphPresentationProjection`

## 背景

StyleIR を svgraph の presentation IR
(`SVGraphPresentationProjection`: masters/layouts/guides/text_styles) に流し込み、
svgraph editor で開けるようにしたい。svgraph の取り込み経路は 2 つあり、要求形が
異なる:

1. **直接 projection を読む消費者** — 正規の `SVGraphPresentationProjection`
   (text_styles は `TextStyleRecord[]`) を期待する。
2. **SVG の `<metadata>` から再構築する `buildSVGraphPresentation`** —
   `presentation.text_styles` が**配列だと各要素を丸ごと `properties` に包む**
   (二重ネスト)。**role キーのオブジェクト** `{role: properties}` だとフラットに
   取り込む。masters/layouts/guides は `obj.id`/`obj.name` を `template_id`/
   `guide_id` に使い、要素全体を `metadata` に保存する。

## 決定

用途別に **2 つの出力関数**を用意する (`src/svgraph/export.ts`)。

- `toSvgraphPresentation(ir)` → 正規の `SVGraphPresentationProjection`
  (text_styles は配列)。`office-style svgraph` CLI と直接消費者向け。
- `toSvgraphIngest(ir)` → svgraph の `buildSVGraphPresentation` 取り込み最適化
  シェイプ:
  - `text_styles` は **role キーのオブジェクト** (二重ネスト回避)
  - 各 master/layout/guide に **`id`** を付与 (template_id/guide_id 保持)
  - `+mj-lt`/`+mn-lt` フォントトークンを実フォント名に解決

プレビュー SVG (`renderPreviewSvg`) の `<metadata>` には `toSvgraphIngest` を埋める。
svgraph 型は実行時依存にせず `src/svgraph/projection.ts` にミラーする (svgraph は
GitHub Packages 公開で認証が要るため)。

## 検証

`examples/svgraph-roundtrip.mjs` (`npm run verify:svgraph`) が実 svgraph CLI
(v0.1.52) にプレビュー SVG を通し、svgraph 側トップレベル presentation に
masters/layouts/guides/text_styles がフラットに流入し、template_id と per-master
theme が保持されることを assert (9/9)。

## 帰結

- pptx → office-style → svgraph editor の流し込みが実機で確立。
- 完全な StyleIR 由来 projection は svgraph の `slides[0].metadata.json` に無損失で
  round-trip する。
- svgraph 側 ingestion 仕様に変更があれば `toSvgraphIngest` の追従が必要 (型ミラー
  と round-trip テストで検知)。
