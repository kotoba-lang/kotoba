# ADR 0001: StyleIR — pptx トーン/マナー/スタイル抽出の 2 層 IR

- Status: Accepted
- Date: 2026-06-24
- 関連: 0002 (slide renderer), 0003 (svgraph interop), 0004 (browser/WebGPU)

## 背景

svgraph / office-causal のいずれにも「アップロードした pptx から visual の
トーン・マナー・スタイルを抽出する」機能が無かった。

- **svgraph**: presentation IR に `masters`/`text_styles`/`guides` の受け皿は
  あるが、入力は SVG のみで pptx リーダが無い。Gemma 4 はテキスト生成専用。
- **office-causal**: pptx は読めるが抽出対象はシェイプ/テキスト/bbox のみ。
  `theme1.xml` / `slideMaster` を読まず、Gemma 4 は因果裁定専用。

両者の中間に「visual からスタイルを抽出して IR 化する層」が欠けていた。

## 決定

新パッケージ `@com-junkawasaki/office-style` を置く。中核は **StyleIR
(`style-ir/1`)** という単一 IR (zod 検証) で、2 つの抽出レイヤがこれを埋める。

### レイヤ 1: 決定論 (OOXML 直読み)

`theme*.xml`(clrScheme 12 色 / fontScheme), `slideMaster*.xml`(背景・
placeholder・p:txStyles), `slideLayout*.xml`(type・placeholder),
`presentation.xml`(sldSz), `viewProps.xml`(guides) を fast-xml-parser で読む。
これらは pptx 内の**確定値**なので vision を使わない (誤差ゼロ・高速・再現可能)。

### レイヤ 2: 解釈 (Gemma 4 vision)

レンダリング済みスライド画像を Gemma 4 (E2B/E4B, transformers.js v4) に入れ、
formality / mood / colorMood / density / visualStyle / summary を `ToneProfile`
として推定。office-causal の `WebGpuGemmaAdjudicator` と同じモデル基盤を
multimodal 化して再利用する。

## なぜ役割分担するか

色・フォント・マスター・ガイドは XML に**構造化された確定値**として存在する。
これを画像から推定するのは誤差を増やすだけで損。逆に「上品/エネルギッシュ/
余白が広い」等の**印象**は XML に無いので vision でしか取れない。
→ 構造 = OOXML、印象 = vision、で重複なく相補的。

## 代替案と却下理由

- **office-causal を拡張**: 因果グラフ IR に視覚スタイルを混ぜると関心が混線。
- **svgraph を拡張**: pptx リーダの新規実装が重く、SVG 中心の設計と齟齬。
- **vision 主体で全部推定**: 確定値まで誤差を持ち込むため不採用 (vision は
  OOXML が無い画像/PDF 入力のフォールバックとしては今後有効)。

## 帰結

- 下流 (テンプレート生成・ブランドガイド準拠チェック・svgraph presentation IR
  への流し込み) は単一 IR を読めばよい。
- IR は part 単位で複数 theme/master を保持できる (`StyleIR.themes`,
  `MasterRecord.theme`) ため、配色・フォントの異なる master が混在するデッキにも
  対応する (詳細は 0002)。
- 実装状況は `docs/STATUS.md` を参照。
