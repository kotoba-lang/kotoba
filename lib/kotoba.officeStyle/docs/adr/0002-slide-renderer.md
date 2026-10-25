# ADR 0002: スライドレンダラと slide-master スタイル継承

- Status: Accepted
- Date: 2026-06-24
- 関連: 0001 (StyleIR)

## 背景

レイヤ 2 (Gemma vision) はスライドの**画像**を必要とする。だが本パッケージは
pptx の構造抽出器であり、PowerPoint/LibreOffice のような忠実レンダラは持たない。
vision に「そのデッキらしい見た目」を与えるための内蔵レンダラが要る。

## 決定

`ppt/slides/*` を SVG 化する PoC レンダラを内蔵する (`src/render/slide-svg.ts`)。
忠実な再現ではなく、**トーンが伝わる近似**を目標とする。

対応:
- 形状: prstGeom (rect / roundRect / ellipse)、custGeom は外接矩形で近似
- 塗り: solidFill / gradFill (SVG linearGradient) / pattFill (fgClr 近似)
- 変形: 回転 (xfrm@rot, 1/60000 度)
- 表: a:tbl (gridCol/tr の寸法でセル矩形 + テキスト)
- 画像: p:pic → グレーのプレースホルダ枠
- 色: テーマ + clrMap で schemeClr/phClr を解決 (0001)

### slide-master スタイル継承 (本 ADR の核)

PowerPoint のテキストは slide → layout → master → master.txStyles → theme の順に
プロパティを継承する。レンダラは各シェイプの placeholder type
(title/ctrTitle→title, body/subTitle/obj→body, その他→other) から master の
txStyles を引き、run が未指定のフォント/サイズ/色/太字を**継承で補完**する。
これにより「マスターで定義した既定スタイル」が空の placeholder にも反映される。

### 複数 master/theme の束ね

各スライドは `slide → slideLayout → slideMaster` の rels チェーン
(`src/extract/links.ts`) で**自分の master** を解決し、その master が rels で
解決した**自分の theme** (配色/フォント) で描画される。1 デッキ内に配色・
フォントの異なる master が混在しても、スライドごとに正しいテーマで描かれる。

## 単位の校正

- `slideSize` / bbox: EMU。px は EMU/9525。
- guide `pos`: OOXML は **1/8 pt** 単位 (4:3 中央ガイド pos=2160 → 270pt=3.75in が
  根拠)。抽出時に `EMU = pos × 12700/8` で EMU 正規化する。

## 代替案

- **svgraph の drawingMlToSvg を使う**: svgraph は完全な pptx を読めず、SVG/
  DrawingML 断片向け。slide ツリー全体の継承解決は本パッケージ側が持つ方が早い。
- **LibreOffice headless で PNG 化**: 高忠実だが重い外部依存。`--vision` で
  外部 PNG を渡す経路として残し、既定は内蔵レンダラとする。

## 帰結

- vision は「実スライド (あれば) or IR プレビュー」の PNG を入力にできる。
- 忠実描画 (任意 custGeom パス・グラデの放射/パス種・SmartArt/グラフ実体) は
  範囲外。必要時は外部 PNG を渡す。
