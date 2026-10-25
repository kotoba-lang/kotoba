(ns kami.mangaka.qa.score
  "スコア集約 (ADR-2607165100)。

  - rubric (0-1 軸) → 0-100 集約: aggregate-score。ai-gftd-mangaka の
    品質ループ (:panel/score) と同スケール。
  - v10 (0-10 軸) → 平均: mean10。v10 の total/heuristic_total は Python 側の
    重み付き合成で、重み定義は退役 runtime と共に失われている — 本 lib は
    **保存された値を正本として素通し** (axes/from-v10) し、重みを捏造しない。
    新規計算には mean10 / aggregate-score を使う。"
  (:require [kotoba.lang.text :as str]
            [kami.mangaka.qa.axes :as axes]))

(defn- clamp [n lo hi] (max lo (min hi n)))

(defn- panel-rect [panel idx]
  (or (:rect panel) (:panel/rect panel)
      [0.05 (+ 0.05 (* idx 0.22)) 0.9 0.2]))

(defn normalize-page-axes
  "VLM JSONのsnake_case/camelCase/string keysをpage18のkebab keywordsへ正規化。
  未知キーと非数値は除外する。"
  [m]
  (let [known (set (map :axis axes/page18))
        ->axis (fn [k]
                 (-> (name k)
                     (str/replace #"([a-z0-9])([A-Z])" "$1-$2")
                     (str/replace "_" "-")
                     str/lower keyword))]
    (into {} (keep (fn [[k v]]
                     (let [axis (->axis k)]
                       (when (and (known axis) (number? v)) [axis v])))) m)))

(defn page-structure
  "EDNだけで評価できるページ構造診断。`:panels` / `:page/panels` の双方を受け、
  0-100 の :layout-geometry と :lettering-load、およびパネル別の容量診断を返す。
  VLMの画風評価とは独立しているため、同じEDNをclj/cljsからqueryできる。"
  [page]
  (let [panels (vec (or (:panels page) (:page/panels page) []))
        rects (mapv panel-rect panels (range))
        valid? (fn [[x y w h]]
                 (and (every? number? [x y w h])
                      (<= 0 x 1) (<= 0 y 1) (pos? w) (pos? h)
                      (<= (+ x w) 1.001) (<= (+ y h) 1.001)))
        overlap (reduce + 0.0
                        (for [[i [ax ay aw ah]] (map-indexed vector rects)
                              [j [bx by bw bh]] (map-indexed vector rects)
                              :when (< i j)]
                          (* (max 0 (- (min (+ ax aw) (+ bx bw)) (max ax bx)))
                             (max 0 (- (min (+ ay ah) (+ by bh)) (max ay by))))))
        layout (if (empty? panels) 0.0
                   (clamp (- (* 100.0 (/ (count (filter valid? rects))
                                          (double (count panels))))
                             (* 900.0 overlap)) 0.0 100.0))
        diagnostics
        (mapv (fn [idx panel rect]
                (let [[_ _ w h] rect
                      bubbles (vec (or (:bubbles panel) (:panel/bubbles panel) []))
                      chars (reduce + 0 (map #(count (str (or (:text %) (:bubble/text %) "")))
                                             bubbles))
                      capacity (max 8.0 (- (* 760.0 (double w) (double h))
                                           (* 3.0 (max 0 (dec (count bubbles))))))
                      load (/ chars capacity)]
                  {:panel/index idx :bubble/count (count bubbles)
                   :character/count chars :character/capacity (long capacity)
                   :lettering/load load :lettering/overflow? (> load 1.0)}))
              (range) panels rects)
        max-load (reduce max 0.0 (map :lettering/load diagnostics))
        lettering (clamp (* 100.0 (- 1.0 (max 0.0 (/ (- max-load 0.72) 0.28))))
                         0.0 100.0)]
    {:axes {:layout-geometry layout :lettering-load lettering}
     :panels diagnostics
     :violations (cond-> []
                   (< layout 70) (conj :invalid-or-overlapping-panels)
                   (some :lettering/overflow? diagnostics) (conj :lettering-overflow))}))

(defn page-review
  "page18 のVLM軸と決定論的構造軸を統合し、採否と修復範囲を返す。
  欠落軸はno-signalとして平均から除外する。threshold未満の軸の :repair を集約し、
  :panel / :layout / :lettering / :mixed を決める。"
  ([vlm-axes structure] (page-review vlm-axes structure 75))
  ([vlm-axes structure threshold]
   (let [known (set (map :axis axes/page18))
         measured (into {} (filter (fn [[k v]] (and (known k) (number? v)))
                                   (normalize-page-axes vlm-axes)))
         weak (vec (for [{:keys [axis repair]} axes/page18
                         :let [v (get measured axis)]
                         :when (and (number? v) (< v threshold))]
                     {:axis axis :score v :repair repair}))
         repairs (set (map :repair weak))
         structural-axes (:axes structure)
         structural-fail? (or (< (get structural-axes :layout-geometry 100) threshold)
                              (< (get structural-axes :lettering-load 100) threshold))
         repairs (cond-> repairs
                   (< (get structural-axes :layout-geometry 100) threshold) (conj :layout)
                   (< (get structural-axes :lettering-load 100) threshold) (conj :lettering))
         scope (cond
                 (empty? repairs) :none
                 (= repairs #{:panel}) :panel
                 (= repairs #{:layout}) :layout
                 (= repairs #{:lettering}) :lettering
                 :else :mixed)
         total (when (seq measured)
                 (let [avg (/ (reduce + 0.0 (vals measured)) (count measured))]
                   (/ (Math/round (* 100.0 avg)) 100.0)))]
     {:accepted (and (seq measured) (empty? weak) (not structural-fail?))
      :total total :threshold threshold :repair-scope scope
      :axes measured :structure structure :weak-axes weak})))

(defn aggregate-score
  "0-1 軸 map の平均 × 100 (四捨五入, int) | nil (数値軸なし = no signal)。
  nil 値の軸は集約前に除外される (no signal は罰しない)。"
  [axes]
  (let [vals (filter number? (vals (or axes {})))]
    (when (seq vals)
      (int (+ 0.5 (* 100 (/ (reduce + 0.0 vals) (count vals))))))))

(defn mean10
  "0-10 軸 map の平均 (double, 1 桁丸め) | nil。:polarity :lower-better の軸を
  反転したい場合は呼び出し側で (- 10 v) してから渡す (重み・反転規則の正本は
  失われているため、本 lib は素直な平均だけを提供する)。"
  [axes]
  (let [vals (filter number? (vals (or axes {})))]
    (when (seq vals)
      (/ (Math/round (* 10.0 (/ (reduce + 0.0 vals) (count vals)))) 10.0))))

(defn merge-perception-axes
  "rubric axes に知覚軸を焼き足す。値が nil の知覚軸は足さない
  (offline = 軸欠落、罰しない)。"
  [axes perception-axes]
  (reduce-kv (fn [m k v] (if (some? v) (assoc m k v) m))
             (or axes {})
             (or perception-axes {})))
