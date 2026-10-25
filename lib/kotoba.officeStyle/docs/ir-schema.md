# StyleIR スキーマ (`style-ir/1`) — 旧設計文書、現行実装とは不一致

**注意**: 本文書は `office-style.runtime` を CLJC へリファクタする前(`0c7e434`
以前)の TypeScript 実装の設計を記述したもので、`src/types.ts` 自体が現行
コードベースに存在しない。現行 `src-cljc/office_style/style.cljk` が実際に
返す StyleIR の形は大幅に単純で、`:office-style/colors`(生 srgbClr/sysClr の
フラットマップ、schemeRef/mods/phClr 解決は無し)・`:office-style/fonts`・
`:office-style/slide-size`・`:office-style/slides`/`:layouts`/`:masters`
(いずれもパート名の文字列一覧のみ、中身は未パース)の5フィールドのみを持つ
(詳細は `README.md` の API 節、または `style.cljc` 本体を正とする)。以下は
将来この方向へ拡張する場合の参考として残す旧設計。

正本は `src/types.ts` の zod スキーマ(現存しない)。`StyleIRSchema.parse(obj)` で検証する。
長さ単位は EMU (914400 EMU = 1 inch、9525 EMU = 1 px @96dpi、12700 EMU = 1 pt)。

## トップレベル

| フィールド | 型 | 説明 |
|---|---|---|
| `version` | `"style-ir/1"` | スキーマ版 |
| `source` | `{ path, app:"ppt" }` | 由来 |
| `slideSize?` | `SlideSize` | `{ cx, cy, unit:"emu", aspect? }` |
| `theme?` | `Theme` | 代表 theme (既定 master の theme) |
| `themes` | `Theme[]` | デッキ全 theme (part 単位で重複排除) |
| `masters` | `MasterRecord[]` | スライドマスター |
| `layouts` | `LayoutRecord[]` | レイアウト |
| `guides` | `GuideRecord[]` | 編集ガイド |
| `textStyles` | `TextStyle[]` | 代表 (既定 master) の既定テキストスタイル |
| `tone?` | `ToneProfile` | vision 解釈 (任意) |

## 主要型

### Theme
```jsonc
{
  "name": "GFTD Brand",
  "colorScheme": { "dk1":{"hex":"#1A1A1A"}, "lt1":{"hex":"#FFFFFF"},
                   "dk2":{...}, "lt2":{...}, "accent1".."accent6":{...},
                   "hlink":{...}, "folHlink":{...} },
  "fontScheme": { "majorFont": {"latin":"Inter","ea":"Noto Sans JP","cs":""},
                  "minorFont": {"latin":"Inter", ...} }
}
```

### Color
```jsonc
{ "hex": "#3B82F6", "schemeRef": "accent1", "mods": { "lumMod": 0.6 } }
```
`schemeRef` は元が schemeClr 参照だった場合の名前。`mods` は lumMod/lumOff/alpha
等 (0..1)。`phClr` は文脈依存のため未解決で残る。

### MasterRecord
```jsonc
{
  "id": "slideMaster1.xml", "name": "...", "part": "ppt/slideMasters/slideMaster1.xml",
  "themePart": "ppt/theme/theme1.xml",
  "theme": { /* この master 自身の Theme */ },
  "background": { "fill": "solid", "color": {"hex":"#FFFFFF"} },
  "placeholders": [ { "type":"title", "idx":null, "bbox": {"x","y","w","h","unit":"emu"} } ],
  "textStyles": [ TextStyle ]
}
```

### LayoutRecord
```jsonc
{ "id":"slideLayout1.xml", "name":"...", "part":"...",
  "type":"title", "masterPart":"ppt/slideMasters/slideMaster1.xml",
  "placeholders": [ Placeholder ] }
```

### TextStyle / TextLevel
```jsonc
{ "role": "title",          // "title" | "body" | "other"
  "levels": [ { "lvl":1, "font": {"latin":"+mj-lt"}, "sizePt":44,
                "bold":true, "italic":false, "color": Color,
                "align":"l" } ] }   // l|ctr|r|just|dist
```

### GuideRecord
```jsonc
{ "orient":"horz", "pos": 3429000, "unit":"emu" }   // 1/8 pt → EMU 正規化済み
```

### ToneProfile (vision 由来)
```jsonc
{ "formality": "formal",           // formal|neutral|casual
  "mood": ["corporate","calm"],
  "colorMood": "cool",              // warm|cool|neutral|monochrome|vivid
  "density": "balanced",            // sparse|balanced|dense
  "visualStyle": ["flat","data-visualization"],
  "summary": "…",
  "confidence": 0.9,
  "evidence": ["ppt/slides/slide1.xml"] }
```

## svgraph 出力との対応

| StyleIR | `toSvgraphPresentation` | `toSvgraphIngest` (SVG metadata 埋め込み用) |
|---|---|---|
| `masters` | `TemplateRecord[]` (kind:"master") | `{id, theme, font_major, accent1, …}[]` |
| `layouts` | `TemplateRecord[]` (kind:"layout") | `{id, type, master}[]` |
| `guides` (EMU) | `GuideRecord[]` (px) | `{id, orientation, position(px), unit}[]` |
| `textStyles` | `TextStyleRecord[]` | **role キーのオブジェクト** `{title:{…}}` |

詳細は ADR 0003。
