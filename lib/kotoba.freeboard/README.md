# freeboard

Apple **Freeform** 風の無限キャンバス・ボード。**clj/cljc が頭脳**（ボードモデル + 操作）、
**描画は host adapter** が `kami-engine-sdk-clj` の render-IR 経由で、
**kasane** が PSD/PDF/PNG/SVG/Sketch/… をキャンバスに取り込み、**kotoba** が
content-addressed な永続/共同編集層 — という分担（`kami-app-sip-clj` と同じ流儀）。

SSoT: `90-docs/adr/2606280200-freeboard-infinite-canvas.md`（superproject 側）

## 構成

| ns | 役割 | テスト |
|---|---|---|
| `freeboard.board` (cljc) | ボード文書 + ビューポート(pan/zoom) + アイテム CRUD + world↔screen + hit-test | ✅ JVM |
| `freeboard.import` (cljc) | kasane `:kasane/doc` → ボードアイテム（ドロップ配置） | ✅ JVM |
| `freeboard.render` (cljc) | ボード → **kami render-IR**（screen-space draw-list, 2D = kami-ui-gpu）+ ECS entity 変換 | ✅ JVM |
| `freeboard.schema` (cljc) | malli = 文書 SSoT（検証） | （malli alias） |

無限キャンバス数学（純粋・検証済み）:
- `screen = (world - pan) * zoom` / `world = pan + screen/zoom`
- `zoom-at` はカーソル下のワールド点を固定したままズーム
- `hit-test` は z 最大のアイテムを返す

## 使い方（モデル）

```clojure
(require '[freeboard.board :as b] '[freeboard.import :as imp] '[freeboard.render :as r])
(-> (b/new-board "My board")
    (b/add-item {:item/kind :sticky :item/x 100 :item/y 100 :item/w 180 :item/h 120 :item/fill "#ffeb8a"})
    (imp/drop-doc kasane-doc [400 200])   ; kasane.normalize の出力をドロップ
    (r/draw-list))                         ; → {:clear [...] :draws [...]}  (host adapter が実行)
```

## テスト / ビルド

```bash
kbb -M:test                            # JVM — 19 tests / 102 assertions（2026-08-13 実測）
kbb --backend sci scripts/run-task.cljk build            # 静的 CLJC/render-IR authority surface を書き出す
```

`kbb -M:test` は **利用できない**。babashka は ADR-2607173000 で本 workspace の
script host から退役し、Wave-3 変換は `scripts/tasks.edn` を空にしたまま
`bb.edn` を消したので、2026-07-17 以降どこからも起動できない
（ADR-2608131600）。復元した babashka 側の本体は `scripts/tasks-complex.edn`
にある。同じ検証は上の `kbb -M:test` が行う。`serve` も同じ理由で
利用できない —— `(shell {:dir "public"} …)` の cwd を `run-task.cljs` が
表現できないため、port が要る。

## 状態（正直に）

- **モデル/インポート/render-IR 生成は実装・検証済み**（当時 bb で 5 tests / 24 assertions green。現在は `kbb -M:test` が全体で 19 tests / 102 assertions green、2026-08-13 実測）。
- **ブラウザ描画/永続 client**は host repo 側で束ねる。ここでは board model / import / render-IR を authority とする。
- **永続/共同編集**（kotoba QuadStore + CACAO）は設計済み・未配線（ADR 参照）。
