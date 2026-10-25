# アーキテクチャ

## データフロー

```
              ┌──────────────────────── 決定論レイヤ (OOXML, vision 不要) ────────────────────────┐
              │                                                                                   │
 .pptx ──► openPackage ──► extractStyleFromPackage ──► StyleIR ─────────────────────────────────┐ │
 (fflate)      (OPC zip)        │  theme / master / layout / guides / slideSize                 │ │
                                │  clrMap 解決 / 複数 master・theme 束ね                          │ │
                                └────────────────────────────────────────────────────────────┐  │ │
                                                                                              ▼  ▼ ▼
              ┌───────────── 解釈レイヤ (Gemma 4 vision) ─────────────┐         ┌──────── 出力 ────────┐
              │                                                       │         │                      │
 StyleIR ─► renderDeckSlides (実スライド) ─┐                          │  StyleIR ─► toSvgraphPresentation ─► svgraph projection
         └─► renderPreviewSvg (代表 1 枚) ─┴─► SVG ─► rasterize ─► PNG ─► Gemma vision ─► ToneProfile
                                                (resvg / canvas)        (cpu/q4 | webgpu/q4f16)  │
                                                                                                 ▼
                                                          aggregateTones (複数スライド) ─► withTone ─► StyleIR{tone}
```

## モジュール構成 (`src/`)

```
ooxml/
  opc.ts          OPC(zip) 展開 + rels 解析            (fflate)
  parse.ts        XML → XmlEl AST + 走査ヘルパ          (fast-xml-parser)
extract/
  color.ts        srgbClr/sysClr/schemeClr → Color
  colormap.ts     clrMap/clrMapOvr 二段解決
  theme.ts        theme*.xml → Theme(clrScheme/fontScheme)
  master.ts       slideMaster/Layout → record + txStyles
  layout-meta.ts  presentation.xml(sldSz) / viewProps.xml(guides)
  links.ts        slide→layout→master→theme rels 解決
  deterministic.ts オーケストレーション → StyleIR
render/
  slide-svg.ts    実スライド → SVG (継承/幾何/塗り/回転/表/画像)
  preview-svg.ts  StyleIR → 代表プレビュー SVG (+svgraph metadata)
  deck.ts         パッケージ → スライド別 SVG (master/theme 束ね)
  rasterize.ts    SVG→PNG (Node, @resvg/resvg-js)
  rasterize-browser.ts  SVG→PNG (ブラウザ, canvas)
vision/
  gemma-vision.ts Gemma 4 multimodal → ToneProfile
svgraph/
  projection.ts   svgraph 型のローカルミラー
  export.ts       toSvgraphPresentation / toSvgraphIngest
pipeline.ts       render→raster→vision→aggregate
types.ts          StyleIR zod スキーマ
index.ts          Node エントリ / browser.ts  ブラウザエントリ
cli.ts            office-style CLI
```

## 設計原則

- **構造は OOXML、印象は vision** (ADR 0001)。確定値を vision で推定しない。
- **単一 IR**。下流 (svgraph 流し込み・ブランド準拠チェック・テンプレ生成) は
  `StyleIR` だけ読めばよい。
- **isomorphic コア**。抽出/描画/svgraph 出力は Node/ブラウザ共通。環境差
  (ラスタライザ・モデル backend) は注入で吸収 (ADR 0004)。
- **検証可能性**。集約・スキーマ・svgraph 整合は vision 非依存でテストできる。

## 依存

- 必須: `fflate` (zip), `fast-xml-parser` (XML), `zod` (スキーマ)
- 任意: `@huggingface/transformers` (vision), `@resvg/resvg-js` (Node raster)
