# canvaskit

board / canvas / viewer の**相互作用(viewport)数学の共通ライブラリ**。用語と
セマンティクスを Apple HIG / UIKit / AppKit に揃えた純 `.cljc`(JVM / CLJS / SCI /
babashka、ランタイム依存ゼロ)。`uikit` / `appkit`(kotoba-ui の screen-shape
binding)と同じ *Kit 系列の、canvas 相互作用担当。

> Skia の CanvasKit とは無関係(`d3` / `torch` / `playwright` と同じ、役割を外部の
> 通用名で名指しする house style)。あちらはラスタライザ、こちらは viewport 数学。

## なぜ

freeboard(`kotoba-lang/freeboard`)と kami-genko(`kotoba-lang/kami-genko`、
freeboard から移植と明記)に同じ viewport 数学(pan / anchored zoom /
world↔screen / hit-test)が**コピーで重複**していた(ADR-2607071130 の調査)。
また `move` のような曖昧語が「オブジェクト移動」と「viewport 移動」を混在させ
やすい。ここに正本を置き、命名は Apple の語彙で固定する:

- **視点を動かす** = scroll / pan(`scroll-by`, `gesture/apply-pan`)
- **オブジェクトを動かす** = move / drag(このライブラリの外 — document model
  (freeboard.board `move-item` 等)の責務)

## 用語対応表

| 一般用語 | canvaskit | Apple 由来 | freeboard / genko 旧名 |
|---|---|---|---|
| viewport / camera | `scroll-view` state | `UIScrollView` | `:freeboard/viewport` `{:x :y :zoom}` |
| pan / drag canvas | `gesture/apply-pan` | `UIPanGestureRecognizer` | `board/pan`, `pan-viewport` |
| scroll(プログラム的) | `scroll-by`, `set-content-offset` | `contentOffset`, `setContentOffset` | — |
| zoom(倍率) | `:zoom-scale` | `zoomScale`, `minimum/maximumZoomScale` | `:zoom` |
| wheel zoom | `gesture/apply-wheel-zoom` | (AppKit `scrollingDeltaY`) | genko `on-wheel` |
| pinch zoom | `gesture/apply-pinch` | `UIPinchGestureRecognizer` | — |
| zoom to selection / fit bounds | `zoom-to-rect` | `zoom(to:animated:)` | —(freeboard 未実装だった) |
| fit to screen | `zoom-to-fit` | — (HIG) | — |
| actual size / reset zoom | `reset-zoom`, `set-zoom-scale` | `setZoomScale` | — |
| jump to / scroll into view | `scroll-rect-to-visible` | `scrollRectToVisible` | — |
| world ↔ screen coordinates | `convert-point-to-view` / `convert-point-from-view`(content ↔ view) | `UICoordinateSpace.convert(_:to:/from:)` | `world->screen` / `screen->world` |
| 表示範囲 | `visible-rect` | `bounds` | — |
| hit test | `hit-test/hit-test`, `point-inside?` | `UIView.hitTest`, `point(inside:with:)` | `board/hit-test`, genko `hit-test` |
| 重なり順 | `:z-position` | `CALayer.zPosition` | `:item/z` |
| 操作の状態機械 | `:possible :began :changed :ended :cancelled` | `UIGestureRecognizer.State` | (ad-hoc な on-down/on-move/on-up) |

## ns 構成

| ns | 役割 |
|---|---|
| `canvaskit.scroll-view` | viewport state + 座標変換 + scroll / zoom の全 op |
| `canvaskit.gesture` | pan / pinch recognizer(純 reducer)+ wheel zoom + scroll-view への適用 |
| `canvaskit.hit-test` | `point-inside?` / z 順 `hit-test`(content・view 両座標) |
| `canvaskit.viewport` | 既存 `{:x :y :zoom}` 形(freeboard / genko)との相互変換ブリッジ |

## 使い方

```clojure
(require '[canvaskit.scroll-view :as sv]
         '[canvaskit.gesture :as g]
         '[canvaskit.hit-test :as ht])

(def s (sv/scroll-view {:bounds [800.0 600.0]}))

;; ドラッグで pan(host は pointer イベントを view 座標で流すだけ)
(def g0 (g/pan-began [10.0 10.0]))
(def g1 (g/pan-changed g0 [30.0 25.0]))
(def s' (g/apply-pan s g0 g1))

;; ホイールでカーソル固定ズーム
(def s'' (g/apply-wheel-zoom s' -500.0 [400.0 300.0]))

;; クリック位置のオブジェクト
(ht/hit-test-in-view s'' items [400.0 300.0])   ; items = {:frame [x y w h] :z-position n}

;; 選択範囲へズーム
(sv/zoom-to-rect s'' [100.0 100.0 400.0 300.0])
```

既存コードからの段階移行(doc 形式を変えない):

```clojure
(require '[canvaskit.viewport :as vp])
(-> (:freeboard/viewport board)
    (vp/from-viewport {:bounds [800.0 600.0]})
    (sv/zoom-to-rect selection-bbox)     ; freeboard に無かった op が使える
    vp/to-viewport)                       ; → {:x :y :zoom} に戻して保存
```

## 境界(やらないこと)

- **描画しない** — render-IR / WebGL / WebGPU は host(kami-engine-sdk 系)の責務。
- **document model を持たない** — アイテムの move / resize / connector / group は
  freeboard.board・kami-genko(genko.cljc)の責務。
- **selection / undo-redo を持たない** — `shitsuke` の `kotoba.editor` kernel の責務。
  hit-test は「何に当たったか」までで、選択集合の管理はしない。

## Verify

```sh
kbb -M:test
```
