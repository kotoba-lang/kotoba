(ns torihiki-chart.view
  "足 → hiccup SVG。純関数、DOM も fetch も持たない。

  ## 色を書かない。しかも `--hig-*` で書く

  この ns に色の literal は 1 つも無い。すべて custom property 参照で、実際の
  値は design system が決める。

  参照するのは **`--hig-*`** であって DADS の `--color-*` ではない。`--hig-*` は
  このワークスペース共通の token 契約（`shitsuke.hig` が発行し、
  `jp-go-dds.tokens/hig->dads` が DADS primitive へ橋渡しする）なので、
  **skin が kotoba-ui でも jp-go-dds でも同じチャートが正しく出る**。DADS の
  `--color-*` を直に参照すると、kotoba-ui skin のページでチャートだけ色を失う
  —— 未定義の custom property は**エラーにならず、その宣言だけが黙って無効に
  なる**（`jp-go-dds.tokens` の docstring が同じ罠を記録している）。

  jp-go-dds skin では bridge の先が DADS primitive なので、`jp-go-dds.dark` の
  反転層に**無改造で追従する** —— チャートだけ light のまま取り残される、が
  起きない。

  上下は `--hig-palette-green` / `--hig-palette-red`。緑が上・赤が下という配色
  そのものは文化依存（日本と台湾の一部では逆）なので、逆にしたい消費者は
  `:up-color` / `:down-color` を渡せる。

  ## SVG の y は下向き

  価格が高いほど上に描かれてほしいので、価格 scale の range は
  `[下端 上端]` の順で渡す（`d3` の `linear-scale` は範囲の向きを問わない）。
  これを逆にすると chart が上下反転し、しかも**エラーにならない**。"
  (:require [kotoba.lang.d3.scale :as scale]
            [torihiki-chart.axis :as axis]
            [torihiki-chart.candle :as candle]))

(def default-opts
  {:width 720
   :height 360
   ;; 右に軸ラベル、下に height ラベルを置くための余白。左は空ける必要が無い
   ;; —— 価格軸を右に置くのは取引所の慣習で、直近値が板と同じ側に来る。
   :pad {:top 8 :right 64 :bottom 20 :left 8}
   ;; 出来高パネルが縦に占める割合。0 で出来高を描かない。
   ;;
   ;; `1/4` ではなく `0.25` と書く。Clojure の Ratio は **ClojureScript の
   ;; 定数になれない**（`clojure.lang.Ratio is not a valid ClojureScript
   ;; constant` でコンパイルが落ちる）。JVM のテストだけでは通ってしまい、
   ;; ブラウザ向けの bundle を作った瞬間に初めて出る。
   ;;
   ;; ここは画素の割合であって集計値ではないので、小数で構わない ——
   ;; 整数で閉じる規律が効くのは `candle` と `axis`（同一性が要る側）。
   :volume-fraction 0.25
   :candle-padding 0.3
   :price-ticks 5
   :height-ticks 6
   :tick-cents 10
   :up-color "var(--hig-palette-green)"
   :down-color "var(--hig-palette-red)"
   :flat-color "var(--hig-color-tertiary-label)"
   :grid-color "var(--hig-color-separator)"
   :label-color "var(--hig-color-secondary-label)"
   :label-size 10})

(defn- px
  "座標を SVG 属性に載せる。整数に丸めるのは、半端な座標が hairline を
  2px にぼかすため（SVG の 1px 線は整数境界に置いたときだけ 1px で出る）。"
  [x]
  #?(:clj (Math/round (double x))
     :cljs (js/Math.round x)))

(defn- colour-of [o c]
  (case (candle/direction c)
    :up (:up-color o)
    :down (:down-color o)
    (:flat-color o)))

(defn- wick
  "ヒゲ。body の中央に 1 本。高値と安値を結ぶ —— **終値と始値ではない**。
  ヒゲを body の範囲で切ると、レンジを見せるという唯一の役目が消える。"
  [o c x->band y colour]
  (let [{:keys [start width]} (x->band (:h c))
        cx (px (+ start (/ width 2)))]
    [:line {:x1 cx :x2 cx
            :y1 (px (y (:high c))) :y2 (px (y (:low c)))
            :stroke colour :stroke-width 1}]))

(defn- body
  "実体。始値と終値の間。

  **高さの下限を 1px にする。** 始値 = 終値の足は高さ 0 になり、SVG は
  高さ 0 の rect を描かない —— 動かなかったブロックだけが chart から消える、
  という一番読み違えやすい欠け方をする。"
  [o c x->band y colour]
  (let [{:keys [start width]} (x->band (:h c))
        y0 (y (:open c))
        y1 (y (:close c))
        top (min y0 y1)
        h (max 1 (- (max y0 y1) top))]
    [:rect {:x (px start) :y (px top)
            :width (max 1 (px width)) :height (px h)
            :fill colour}]))

(defn- volume-bar [o c x->band vy base colour]
  (let [{:keys [start width]} (x->band (:h c))
        top (vy (:volume c))]
    [:rect {:x (px start) :y (px top)
            :width (max 1 (px width)) :height (max 1 (px (- base top)))
            :fill colour :opacity 0.45}]))

(defn candle-chart
  "足のベクタ → `[:svg …]` hiccup。

  `opts` は `default-opts` にマージされる。`:candles` は
  `torihiki-chart.candle/candles` の出力（height 昇順）。

  足が無いときは**空の枠ではなく nil** を返す。空の軸だけが描かれた枠は
  『データが無い』ではなく『価格が無い』に見え、後者は嘘。呼び出し側が
  『まだ約定がありません』と書く方が正しい。"
  [opts]
  (let [o (merge default-opts opts)
        cs (vec (:candles o))]
    (when (seq cs)
      (let [{:keys [width height pad volume-fraction candle-padding]} o
            plot-l (:left pad)
            plot-r (- width (:right pad))
            plot-t (:top pad)
            plot-b (- height (:bottom pad))
            vol-h (* (- plot-b plot-t) volume-fraction)
            price-b (- plot-b vol-h)
            [lo hi] (candle/extent cs)
            ;; 上下に 1 目盛り分の余白を作らない —— 高値がちょうど枠に触るのは
            ;; 正しい。触っていることが情報。
            y (scale/linear-scale [lo hi] [price-b plot-t])
            vmax (candle/volume-max cs)
            vy (scale/linear-scale [0 (max 1 vmax)] [plot-b (+ price-b 2)])
            x->band (scale/band-scale (map :h cs) [plot-l plot-r] candle-padding)
            price-tick-vals (axis/ticks [lo hi] (:price-ticks o))
            h-tick-vals (axis/height-ticks (map :h cs) (:height-ticks o))]
        (into
         [:svg {:viewBox (str "0 0 " width " " height)
                :width "100%" :height height
                :role "img"
                ;; スクリーンリーダには『チャート』ではなく実際の値域を渡す。
                ;; 図形は読めないが、レンジと足数は読める。
                :aria-label (str "ブロック足 " (count cs) " 本、"
                                 (axis/format-usd (:tick-cents o) lo) " から "
                                 (axis/format-usd (:tick-cents o) hi) "、"
                                 (axis/format-height (:h (first cs))) " から "
                                 (axis/format-height (:h (peek cs))))}]
         (concat
          ;; 価格グリッドと右側ラベル
          (for [t price-tick-vals]
            [:g
             [:line {:x1 plot-l :x2 plot-r :y1 (px (y t)) :y2 (px (y t))
                     :stroke (:grid-color o) :stroke-width 1}]
             [:text {:x (+ plot-r 6) :y (+ (px (y t)) 3)
                     :fill (:label-color o) :font-size (:label-size o)
                     ;; 数字が揃わないと軸として読めない。
                     :style "font-variant-numeric: tabular-nums"}
              (axis/format-usd (:tick-cents o) t)]])
          ;; 出来高（価格より先に描いて後ろに置く）
          (when (pos? volume-fraction)
            (for [c cs]
              (volume-bar o c x->band vy plot-b (colour-of o c))))
          ;; 足
          (for [c cs]
            (let [colour (colour-of o c)]
              [:g (wick o c x->band y colour)
               (body o c x->band y colour)]))
          ;; height ラベル
          (for [h h-tick-vals]
            (let [{:keys [start width]} (x->band h)]
              [:text {:x (px (+ start (/ width 2))) :y (- height 6)
                      :text-anchor "middle"
                      :fill (:label-color o) :font-size (:label-size o)
                      :style "font-variant-numeric: tabular-nums"}
               (axis/format-height h)]))))))))
