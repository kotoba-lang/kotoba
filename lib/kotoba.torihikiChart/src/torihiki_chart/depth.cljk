(ns torihiki-chart.depth
  "板 → 深度図。tape の 200 件制限を受けない唯一のチャート。

  node の `/book` は `{:bids [{:level :qty :cum}] :asks [...]}` を返し、`:cum`
  は既に累積されている（`torihiki.api/book-snapshot` が数える）。**ここで
  数え直さない** —— 同じ量を二箇所で計算すれば、いつか食い違う。

  ## 階段で描く。折れ線で描かない

  板の深さは価格の連続関数ではない。ある価格帯に注文が無ければ深さはそこで
  平らで、次の板がある価格で垂直に跳ぶ。折れ線で結ぶと**存在しない価格に
  存在しない流動性**を描くことになり、それはちょうど『薄い板でも滑らかに
  約定できそうに見える』という、一番高くつく嘘。

  ## bid は右から左、ask は左から右

  中央（best bid / best ask の間）から外側へ累積が増える。板の遠い側ほど
  深いのが正しい向きで、逆に描くと『中央が一番厚い』という板の性質と反対の
  絵になる。"
  (:require [kotoba.lang.d3.scale :as scale]
            [torihiki-chart.axis :as axis]))

(def default-opts
  {:width 720
   :height 200
   :pad {:top 8 :right 64 :bottom 20 :left 8}
   :price-ticks 5
   :tick-cents 10
   :bid-color "var(--hig-palette-green)"
   :ask-color "var(--hig-palette-red)"
   :grid-color "var(--hig-color-separator)"
   :label-color "var(--hig-color-secondary-label)"
   :label-size 10})

(defn- px [x]
  #?(:clj (Math/round (double x))
     :cljs (js/Math.round x)))

(defn staircase
  "`levels`（`{:level :cum}` の seq）→ 階段の点列 `[[x y] …]`。

  各板で『前の深さのまま新しい価格へ水平移動 → その価格で垂直に上がる』の
  2 点を出す。`d3` の `line-generator` はこの点列をそのまま結べば階段になる
  —— 曲線補間を持たないのが、ここでは利点。

  `levels` は best から遠い順に並んでいる必要がある（`:cum` が単調増加）。"
  [levels x y]
  (loop [[l & more] (seq levels)
         prev nil
         acc []]
    (if (nil? l)
      acc
      (let [xx (x (:level l))
            yy (y (:cum l))
            acc (if prev (conj acc [xx (y prev)]) acc)]
        (recur more (:cum l) (conj acc [xx yy]))))))

(defn- side-path
  "階段を面として閉じる。`baseline` は深さ 0 の y。

  面にするのは、深さが『そこまでの総量』であることを見せるため。線だけだと
  上端の輪郭にしか見えず、累積であることが読めない。"
  [pts baseline]
  (when (seq pts)
    (let [[x0] (first pts)
          [xn] (peek pts)]
      (str "M" x0 "," baseline
           (apply str (for [[x y] pts] (str "L" x "," y)))
           "L" xn "," baseline "Z"))))

(defn depth-chart
  "板 snapshot → `[:svg …]` hiccup。

  `opts` に `:bids` `:asks`（node の `/book` の形）を渡す。どちらも空なら
  **nil** を返す —— 空の枠は『板が無い』ではなく『深さが 0』に見え、後者は
  板が実在して薄いという別の状態。

  価格軸は bid の最安から ask の最高まで。片側しか無い板でもそのまま描ける
  （実際に起きる: 片側が全部約定した直後）。"
  [opts]
  (let [o (merge default-opts opts)
        bids (vec (:bids o))
        asks (vec (:asks o))]
    (when (or (seq bids) (seq asks))
      (let [{:keys [width height pad]} o
            plot-l (:left pad)
            plot-r (- width (:right pad))
            plot-t (:top pad)
            plot-b (- height (:bottom pad))
            levels (map :level (concat bids asks))
            lo (reduce min levels)
            hi (reduce max levels)
            cmax (reduce max 1 (map :cum (concat bids asks)))
            x (if (= lo hi)
                (constantly (/ (+ plot-l plot-r) 2))
                (scale/linear-scale [lo hi] [plot-l plot-r]))
            y (scale/linear-scale [0 cmax] [plot-b plot-t])
            ;; bid は best（高値）から遠い（安値）へ累積するので、x が小さく
            ;; なる向きに階段が伸びる。node は best 順で返すのでそのまま。
            bid-pts (staircase bids x y)
            ask-pts (staircase asks x y)
            price-tick-vals (axis/ticks [lo hi] (:price-ticks o))]
        (into
         [:svg {:viewBox (str "0 0 " width " " height)
                :width "100%" :height height
                :role "img"
                :aria-label (str "板の深度 "
                                 (axis/format-usd (:tick-cents o) lo) " から "
                                 (axis/format-usd (:tick-cents o) hi)
                                 "、最大累積 " (axis/format-lots cmax))}]
         (concat
          (for [t price-tick-vals]
            [:line {:x1 (px (x t)) :x2 (px (x t)) :y1 plot-t :y2 plot-b
                    :stroke (:grid-color o) :stroke-width 1}])
          ;; `mapv` であって `map` ではない。`side-path` は `peek` で末尾を取り、
          ;; LazySeq に `peek` は ClassCastException になる（実測）。
          (when-let [d (side-path (mapv (fn [[a b]] [(px a) (px b)]) bid-pts) plot-b)]
            [[:path {:d d :fill (:bid-color o) :opacity 0.35}]
             [:path {:d d :fill "none" :stroke (:bid-color o) :stroke-width 1}]])
          (when-let [d (side-path (mapv (fn [[a b]] [(px a) (px b)]) ask-pts) plot-b)]
            [[:path {:d d :fill (:ask-color o) :opacity 0.35}]
             [:path {:d d :fill "none" :stroke (:ask-color o) :stroke-width 1}]])
          (for [t price-tick-vals]
            [:text {:x (px (x t)) :y (- height 6) :text-anchor "middle"
                    :fill (:label-color o) :font-size (:label-size o)
                    :style "font-variant-numeric: tabular-nums"}
             (axis/format-usd (:tick-cents o) t)])))))))
