(ns kami.mangaka.qa.overlay
  "Annotated page overlay — v10 世代の scored.png (パネル番号 + 読み順パス +
  顔/gaze ボックス + スコアヘッダ) を、ピクセル合成でなく **純 hiccup SVG**
  として再現する renderer (ADR-2607165100 addendum 1)。

  I/O ゼロ・DOM 依存ゼロ — hiccup vector を返すだけなので、cljs (reagent /
  kotoba-ui) ではそのまま component になり、nbb / JVM では同梱の ->svg-str
  (最小シリアライザ) で静的 SVG 文字列にできる。ベース画像は :image-href
  (URL でも data URI でも) として <image> に敷く。

  入力座標はすべて正規化 0..1 (kami.mangaka.qa.geometry と同じ規約) — VLM
  検出 (detect-panels / detect-faces) の出力も、authored な page record の
  gaze box も、そのまま渡せる。内部では viewBox のユーザー単位に展開する。"
  (:require [kotoba.lang.text :as str]))

(def palette
  {:panel "#7c4dff"      ; パネル枠 + 読み順 (v10 overlay の紫系)
   :face  "#00bfa5"      ; 顔/gaze ボックス (teal)
   :text  "#ffffff"
   :header "#111111"})

(defn- f1 [v] (/ (Math/round (* 10.0 (double v))) 10.0))

(defn- rect-center [{:keys [x y w h]}]
  [(+ x (/ w 2.0)) (+ y (/ h 2.0))])

(defn face->rect [{:keys [cx cy w h]}]
  {:x (- cx (/ w 2.0)) :y (- cy (/ h 2.0)) :w w :h h})

(defn annotated-page
  "Annotated page の hiccup SVG。
  opts: {:image-href <url|data-uri>     ; ベース画像 (省略可)
         :title \"p01 …\"               ; ヘッダ表題 (省略可)
         :header-entries [[:total 79.1] [:tier \"mid\"] …]
         :panels [{:x :y :w :h} …]      ; 読み順 (番号バッジ + パス)
         :faces  [{:cx :cy :w :h} …]
         :aspect [w h]}                  ; viewBox (既定 [744 1052] ≈ B5)"
  [{:keys [image-href title header-entries panels faces aspect]
    :or {aspect [744 1052]}}]
  (let [[aw ah] aspect
        X (fn [v] (f1 (* v aw)))
        Y (fn [v] (f1 (* v ah)))
        fs (f1 (* 0.022 ah))                       ; 基準フォント
        badge-r (f1 (* 0.024 aw))
        stroke (max 1.5 (f1 (* 0.004 aw)))
        panels (vec (or panels []))
        faces (vec (or faces []))]
    (-> [:svg {:xmlns "http://www.w3.org/2000/svg"
               :viewBox (str "0 0 " aw " " ah)
               :width "100%"}]
        (cond->
          image-href
          (conj [:image {:href image-href :x 0 :y 0 :width aw :height ah
                         :preserveAspectRatio "xMidYMid slice"}]))
        ;; パネル枠
        (into (map (fn [p]
                     [:rect {:x (X (:x p)) :y (Y (:y p))
                             :width (X (:w p)) :height (Y (:h p))
                             :fill "none" :stroke (:panel palette)
                             :stroke-width stroke :stroke-opacity 0.85}])
                   panels))
        ;; 顔/gaze ボックス
        (into (map (fn [fb]
                     (let [r (face->rect fb)]
                       [:rect {:x (X (:x r)) :y (Y (:y r))
                               :width (X (:w r)) :height (Y (:h r))
                               :fill "none" :stroke (:face palette)
                               :stroke-width stroke :stroke-opacity 0.9}]))
                   faces))
        ;; 読み順パス
        (cond->
          (seq (rest panels))
          (conj [:polyline
                 {:points (str/join " " (map (fn [p]
                                               (let [[cx cy] (rect-center p)]
                                                 (str (X cx) "," (Y cy))))
                                             panels))
                  :fill "none" :stroke (:panel palette)
                  :stroke-width stroke :stroke-opacity 0.75
                  :stroke-dasharray (str (* 3 stroke) " " (* 2 stroke))}]))
        ;; パネル番号バッジ
        (into (mapcat (fn [[i p]]
                        (let [[cx cy] (rect-center p)]
                          [[:circle {:cx (X cx) :cy (Y cy) :r badge-r
                                     :fill (:panel palette) :fill-opacity 0.92}]
                           [:text {:x (X cx) :y (Y cy)
                                   :fill (:text palette) :font-size (f1 (* 1.1 fs))
                                   :text-anchor "middle" :dominant-baseline "central"
                                   :font-family "sans-serif" :font-weight "bold"}
                            (str (inc i))]]))
                      (map-indexed vector panels)))
        ;; スコアヘッダ
        (cond->
          title
          (into [[:rect {:x 0 :y 0 :width aw :height (f1 (* 2.0 fs))
                         :fill (:header palette) :fill-opacity 0.85}]
                 [:text {:x (f1 (* 0.5 fs)) :y (f1 (* 1.3 fs))
                         :fill (:text palette) :font-size fs
                         :font-family "sans-serif" :font-weight "bold"}
                  (str title
                       (when (seq header-entries)
                         (str "   "
                              (str/join "  " (map (fn [[k v]] (str (name k) "=" v))
                                                  header-entries)))))]])))))

(defn ->svg-str
  "最小 hiccup→SVG 文字列シリアライザ (この overlay の出力形だけを対象:
  keyword tag + attrs map + 子は vector/seq/string/number)。nbb / JVM の
  静的生成用 — cljs アプリでは hiccup をそのまま render する方が良い。"
  [node]
  (cond
    (vector? node)
    (let [[tag & more] node
          [attrs children] (if (map? (first more))
                             [(first more) (rest more)]
                             [{} more])
          tag-name (name tag)
          attr-str (str/join "" (map (fn [[k v]]
                                       (str " " (name k) "=\""
                                            (-> (str v)
                                                (str/replace "&" "&amp;")
                                                (str/replace "\"" "&quot;"))
                                            "\""))
                                     attrs))
          body (str/join "" (map ->svg-str children))]
      (if (seq body)
        (str "<" tag-name attr-str ">" body "</" tag-name ">")
        (str "<" tag-name attr-str "/>")))
    (sequential? node) (str/join "" (map ->svg-str node))
    (nil? node) ""
    :else (-> (str node)
              (str/replace "&" "&amp;")
              (str/replace "<" "&lt;"))))
