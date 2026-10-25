# kasane（重ね）

[![CI](https://github.com/kotoba-lang/kasane/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kasane/actions/workflows/ci.yml)

Adobe(AI/PSD) を **外部依存ゼロの純 cljc + EDN データ駆動文法**で扱うライブラリ。
binary 文法を EDN で宣言し、小さな純 cljc エンジンで解析する（Kaitai Struct を
EDN データ + Clojure 解釈で再構成）。

SSoT: `90-docs/adr/2606272100-adobe-edn-kasane.md`（superproject 側）

## 構成（コアエンジン + kasane 自身の native フォーマット、外部依存ゼロ）

| ns | 役割 | WASM(kotoba-clj) |
|---|---|---|
| `kasane.bytes` | byte cursor + read primitive（u8/u16/u32/i*・endian・固定長） | 未検証* |
| `kasane.decode` | **EDN 文法を解釈する純エンジン** `(decode grammar bytes)→EDN` | 未検証* |
| `kasane.codec` | PackBits（PSD :rle channels 用） | 未検証* |
| `kasane.normalize` | raw → 共通 `:kasane/doc` モデル（PSD/BMP/Sketch 用に加え、外部
  フォーマットrepo の生 parse 出力からも呼べる純関数群 — 下記参照） | 未検証* |
| `kasane.schema` | **malli = 共通モデルの SSoT**（検証/生成。WASM 経路外） | ✕ |
| `kasane.gltf` / `kasane.svg` / `kasane.json` | glTF/SVG/JSON —
  既存 reverse-domain 姉妹repoへの薄い adapter（2026-07-08 統合済み。詳細は下記） | 未検証* |
| `resources/kasane/grammar/{psd,bmp}.edn` | kasane 自身の native フォーマット文法（データ） | data |

**\* 2026-07-08 追記: 「○」表記は未検証の想定だったと判明、「未検証」に訂正した。**
実際に `kotoba-lang/kotoba` の `kotoba wasm emit`（現行実装、Clojureベース
`src/kotoba/{runtime,launcher,wasm_exec}.clj` — AGENTS.md が言及する独立
Rust repo `kotoba-clj` は存在せず、この Clojure 実装がそれに相当する）で
`org-ietf-deflate`（このバッチで最も単純・移植性の高いnamespace）のコンパイルを
試したところ、`kotoba.runtime/check` の内部で `ClassCastException`
（`symbol-key`: `PersistentVector cannot be cast to Named`）が発生し
クラッシュした。関数パラメータの map destructuring（`{:keys [...]}`）を
除去しても別の場所で同じ例外が再発し、原因を完全に特定するには至っていない
——「unsupported construct」という綺麗な診断ではなく生の内部例外である点も
含め、コンパイラが実際にサポートするEDN-subsetは各READMEの想定より狭い
可能性が高い。`kotoba-lang/kotoba` 側の対応は本batchのスコープ外（この
kasane/utsushi分解バッチでは、コンパイラ自体を直さず「未検証」と正直に
表記するだけに留める）。

## 2026-07 分解: 個別フォーマットのDSLを reverse-domain 名の別リポジトリへ抽出

このリポジトリはもともと PSD/PDF/PNG/JPEG/GIF/TIFF/ZIP/TTF/WOFF/ISOBMFF/EPUB/ODF
等、十数個の独立した外部フォーマット仕様を1リポジトリに同居させていた。kotoba-lang
の既存命名規約（`org-<標準化団体>-<spec>` reverse-domain 命名、ADR-2607052300 以降）
に揃えるため、`kasane` 固有でない各フォーマットの実装を個別リポジトリへ抽出した
（`com-junkawasaki/root` ADR 精度2607072500 の pdk→org-synopsys-liberty/org-si2-lef
分離と同型のバッチ）。

| 旧 ns | 移動先 |
|---|---|
| `kasane.codec.inflate`（DEFLATE/zlib） | [`org-ietf-deflate`](https://github.com/kotoba-lang/org-ietf-deflate) |
| `kasane.png` | [`org-w3-png`](https://github.com/kotoba-lang/org-w3-png) |
| `kasane.gif` | [`org-compuserve-gif`](https://github.com/kotoba-lang/org-compuserve-gif) |
| `kasane.tiff` | [`org-adobe-tiff`](https://github.com/kotoba-lang/org-adobe-tiff) |
| `kasane.zip` | [`org-pkware-zip`](https://github.com/kotoba-lang/org-pkware-zip) |
| `kasane.jpeg` + `kasane.jpeg.decode` | [`org-iso-jpeg`](https://github.com/kotoba-lang/org-iso-jpeg) |
| `kasane.ttf` | [`org-iso-opentype`](https://github.com/kotoba-lang/org-iso-opentype) |
| `kasane.woff` | [`org-w3-woff`](https://github.com/kotoba-lang/org-w3-woff) |
| `kasane.isobmff` | [`org-iso-isobmff`](https://github.com/kotoba-lang/org-iso-isobmff)（`utsushi` の MP4 demux/mux/remux と統合） |
| `kasane.cos`（PDF） | [`org-iso-pdf`](https://github.com/kotoba-lang/org-iso-pdf) |
| epub->doc | [`org-w3-epub`](https://github.com/kotoba-lang/org-w3-epub) |
| odf->doc | [`org-oasis-odf`](https://github.com/kotoba-lang/org-oasis-odf) |

## 2026-07-08 追記: gltf/svg/json は既存姉妹repoへの薄い adapter に統合済み

- `kasane.json` → [`kotoba-lang/json`](https://github.com/kotoba-lang/json)
  （`json.core/decode`）に委譲。既存repoは string-keyed map を返すため、
  kasane側の元契約（keyword-keyed map、`kasane.gltf`/`sketch->doc` の
  `(:_class layer)` 等が前提）を保つ keywordize wrapper を追加。
- `kasane.svg` → [`org-w3-svg`](https://github.com/kotoba-lang/org-w3-svg)
  （新設 `svg.reader` ns）に委譲。既存 `svg.core/attrs` は EDN要素→属性map
  （write側）で、kasaneが必要とする「属性文字列→map」（read側）とは入力形状が
  違うため、衝突を避けて `svg.reader` という別nsに read側を追加した。
- `kasane.gltf` → [`org-khronos-glb`](https://github.com/kotoba-lang/org-khronos-glb)
  （`glb/parse-glb` + `glb.json/parse`）に委譲。org-khronos-glb は「reader追加」
  を要さず既に kasane.gltf と同等のGLBチャンク読み取り+生JSONパースを持って
  いたため委譲で済んだ。**訂正（2026-07-08 再調査）**: org-khronos-glb は
  自身のREADMEで "no glTF-JSON schema knowledge (accessors, meshes,
  materials, ...)" と明言しており、accessor/mesh decodeは実装していない
  （前回記載の「accessor decodeまで含む完全実装」は誤り）。
  `kasane.normalize/gltf->doc` 自体が node/mesh/scene の**個数**とtransform
  だけを生JSONから読む薄い射影で、accessor decodeを元々必要としていないため
  実害は無いが、READMEの表記を実態に合わせて訂正する。

## 2026-07-08 追記2: OOXML投影も JVM 依存を持ち込まずに統合完了

`kasane.normalize/ooxml->doc` は [`kotoba-lang/ooxml`](https://github.com/kotoba-lang/ooxml)
（format検出 `package-kind` + PowerPoint複数スライドの数値順ソート
`office-parts` — 両方とも reader-conditional 無しの100%移植可能な純関数）と
[`kotoba-lang/office`](https://github.com/kotoba-lang/office) の
`office.graph/part-graph`（Word本文テキスト抽出。数値HTMLエンティティ
`&#x...;`をkasane自前の旧実装より正しくデコードする、こちらも純関数）に
委譲した。**`office.opc/open-package`/`package-bytes`（JVM専用、
`java.util.zip`直接依存）は一度も呼ばない** — kasaneは引き続き
`org-pkware-zip`で既にunzip済みのentriesを受け取り、`:office/entries`
map を自前で組み立てる。同じ`office`リポジトリ内に JVM専用nsが同居していても、
cljcのreader-conditionalのおかげで**実際に呼ぶ関数が移植可能なら依存側は
汚染されない**（未使用の`#?(:clj ...)`分岐はcljs/wasmターゲットではただの
コンパイル時分岐で、ランタイムに漏れない）。

Excel テキスト（実データは`xl/sharedStrings.xml`にあり、`ooxml.core`の
worksheet専用パターンからは直接届かない）と PowerPoint シェイプ geometry
（bbox/fill/preset geometry — 他のどのrepoもまだ持っていない）は
kasane自前のregexロジックのまま維持。

副産物として、PowerPoint複数スライドの並び順が「zipエントリの物理順」から
`ooxml.core`の数値ソート（`slide2` < `slide10`）に修正された（元実装は
辞書順でズレる可能性があった）。

kasane に残るのは: EDN文法エンジン本体、共通 `:kasane/doc` モデル（他repoの
parse出力も受けられる純粋な射影関数として）、そして PSD/BMP/Sketch という
kasane 自身の flagship native フォーマット。これで最初のバッチADRで挙げた
follow-up 4件（gltf/svg/json/ooxml）はすべて完了。

## 使い方

```clojure
(require '[clojure.edn :as edn] '[clojure.java.io :as io]
         '[kasane.decode :as d] '[kasane.normalize :as norm])

(let [g   (edn/read-string (slurp (io/resource "kasane/grammar/psd.edn")))
      raw (d/decode g (slurp-bytes "design.psd"))]   ; bytes = seq of 0-255
  (norm/->doc :psd raw))
;; => #:kasane{:format :psd
;;             :canvas {:width 4 :height 3 :unit :px :color-mode :rgb ...}
;;             :nodes [#:node{:kind :raster :blend :normal :bbox [1 2 2 3] ...}]}
```

EDN 文法は宣言的データ:

```clojure
{:meta  {:endian :big :root :psd-file}
 :enums {:color-mode {3 :rgb 4 :cmyk ...}}
 :types {:psd-file [{:id :sig :type :magic :value "8BPS"}
                    {:id :width :type :u32} ...]}}
```

## テスト

```bash
kbb -M:test                                       # JVM test-runner（全6 ns、ooxml-testも含む）
kbb --backend sci -cp "$(kbb -A:test -Spath)" test/run.cljk  # nbb（cljs on Node、AGENTS.mdのruntime優先順位で
                                                        # JVM単体より上位）— 5 ns（ooxml-testを除く）
```

**2026-07-08、babashka(`bb`)からnbbへ移行**（AGENTS.mdの`.cljc`ランタイム優先順位
`kotoba wasm > clojurewasm > cljs > nbb > jvm`に揃える）。移行の過程で
`kasane.bytes/sint!`の実バグを発見・修正した: `bit-shift-left`はJVMではLong
（64bit）で安全だが、cljs/JSでは32bit符号付き整数+shift量mod32という別物の
セマンティクスになり（`1 << 32` は `1`、`1 << 31` は負数）、32bit符号拡張の
閾値計算が静かに壊れていた（**JVM上のテストは全部greenのまま気付かれなかった
— cljc設計が謳う「同じコードがJVM/cljs/kotoba-wasmで動く」を実際にcljs上で
検証していなかったことの実例**）。乗算ベースの`pow2`ヘルパーに置き換えて修正
（`src/kasane/bytes.cljk`参照）。同様の理由でtestヘルパーの`(mapv int s)`
（文字→コードポイント、JVMのCharacterでしか動かない）も
`#?(:clj (int c) :cljs (.charCodeAt c 0))`という既存の移植可能パターン
（`kasane.cos`由来、org-iso-pdfに継承済み）に統一した。

**既知の制限**: `kasane.json`が委譲している`kotoba-lang/json`の`\u`unicode
エスケープ処理に同種のバグ（`(int ch)`をcljsの文字に対して誤用）を発見した
（`kasane.json-test`の`structures`テストがnbb実行時のみ1件fail）。別repoの
問題のためこのバッチでは未修正 — 上流での修正が必要。

`kasane.ooxml-test`は`.clj`（`.cljc`でない）ため nbb では実行されない —
fixture生成に`java.util.zip.ZipOutputStream`（JVM専用）を使っており、この
依存グラフには移植可能なzip **writer**がまだ存在しない（`org-pkware-zip`は
readerのみ）。`kbb -M:test`では引き続き実行される。

## R0 スコープ / 既知の限界（ADR-2606272100）

- **PSD**: ヘッダ・color-mode/image-resource blob・レイヤレコードまで。channel image data は
  layer-and-mask の length で skip。
- raster ピクセル実体は EDN/git にインラインせず B2+DataLad の CID 参照（AGENTS.md 規律）。
- WASM 化は `kotoba wasm emit` の EDN-subset 成熟に追随する想定だったが、
  2026-07-08 時点で実際に試すと内部クラッシュする（上記構成表の脚注参照）—
  「段階適用」以前に現状は未達。
