# kasane × kotoba-clj WASM readiness（正直な評価）

ADR-2606272100 は「`kasane.decode`/`inflate` 等を kotoba-clj で WASM Component 化する」
ことを将来像として掲げる。本書は**現時点の適合性を誇張せず**記録する。

## kotoba-clj の EDN-subset（受理範囲）

kotoba AGENTS.md より、現状サポートされるのはおおむね:

- `def`/`defn`/`ns`、`if`/`when`/`let`/`do`、`+ - * / mod`、`= < > <= >=`、`and or not`
- 文字列リテラル + `str-len`/`byte-at`（文字列 = packed handle）
- ユーザー関数呼び出し（相互再帰含む）、`loop`/`recur`、byte-builder
- `list<u8>` の Component 入出力、in-guest CBOR decode/encode、kqe host builtins

**未サポート（kasane が依存しているもの）**: 永続 map / set、`atom`/`volatile!`、transient、
host 配列（`double-array` 等）、protocol/record、`nth` on 任意コレクション、可変長 keyword map。

## kasane 各 ns のギャップ

| ns | subset 適合 | 阻害要因 |
|---|---|---|
| `kasane.codec` の `packbits` | △ 近い | `vec`/`nth`/`into`/`loop`。出力を byte-builder に替えれば候補筆頭 |
| `kasane.bytes` | ✕ | cursor 位置を **atom** で保持。→ 位置を loop/recur で**引き回す**純設計に要書換 |
| `kasane.codec.inflate` | ✕ | bit reader が atom、Huffman 表が **map**、出力が `volatile!`+vector。→ Huffman を**フラット配列/関数**化、状態を int で thread、出力 byte-builder へ |
| `kasane.decode`（文法エンジン） | ✕ | 文法・ctx が **map**、keyword 多用。map がサブセットに入るまで困難 |
| `kasane.cos` / `kasane.tiff` / `kasane.jpeg.decode` | ✕ | map・float・配列。JVM/cljs 専用 |
| `kasane.schema`(malli) / `kasane.quads` | ✕（設計上） | 検証/射影専用、WASM 経路外 |

## 進め方（2 案）

1. **kotoba-clj の言語成長**（推奨・本命）: 永続 map / `atom` 相当 / byte-vector を subset に
   追加 → kasane を概ねそのまま載せられる。kotoba 側 workstream マター。
2. **subset 狙いの hot-path 書換**（先行可能）: atom/map を使わず
   - `packbits`: 出力を byte-builder、入力 index を recur で thread（atom 不要）。
   - `inflate`: bit 状態(byte-pos, bit-pos, 32bit acc)を int で thread、Huffman を
     **canonical 配列**（first-code/offset 方式）で表に頼らず復号、出力 byte-builder。
   - これらは `list<u8> → list<u8>` の Component として kotoba-clj `run` に乗る。

## 現状の正直な結論

**今日の kasane は JVM/cljs で動く**（bb で全テスト green）。WASM 化は上記いずれかが要る
段階で、「そのまま WASM で動く」状態ではない。ADR-2606272100 の ns 表の「WASM ○」は
**到達目標（aspirational）**であって現状ではない、と本書で明確化する。最初の WASM 実証は
**packbits → flat-table inflate** の順が現実的（map 不要、byte-builder 出力で subset に収まる）。
