(ns kami.mangaka.qa.geometry
  "純幾何 QA (ADR-2607165100) — 検出源 (VLM / authored gaze box / 将来の
  ネイティブ CV) を問わず同じ式が使える、正規化 0..1 座標系の矩形演算。

  座標規約: 顔は {:cx :cy :w :h} (中心+サイズ)、パネル/吹き出しは
  {:x :y :w :h} (左上+サイズ)。v10 世代の annotated page (gaze box /
  readingPath overlay) の box も同じ規約に正規化して通せる。"
  )

(defn face->rect
  "{:cx :cy :w :h} → {:x :y :w :h} (左上系)。"
  [{:keys [cx cy w h]}]
  {:x (- cx (/ w 2.0)) :y (- cy (/ h 2.0)) :w w :h h})

(defn overlap-area
  "2 つの {:x :y :w :h} の交差面積。"
  [a b]
  (let [x1 (max (:x a) (:x b))
        y1 (max (:y a) (:y b))
        x2 (min (+ (:x a) (:w a)) (+ (:x b) (:w b)))
        y2 (min (+ (:y a) (:h a)) (+ (:y b) (:h b)))]
    (* (max 0.0 (- x2 x1)) (max 0.0 (- y2 y1)))))

(defn bubble-clearance
  "吹き出し群が顔をどれだけ覆っていないか → 0..1 (1 = どの顔も覆われて
  いない)。各顔の「覆われ率」(全吹き出しとの交差面積合計 / 顔面積) の最悪値を
  1 から引く。吹き出しか顔が無ければ 1 (問題なし)。"
  [bubbles faces]
  (if (or (empty? bubbles) (empty? faces))
    1.0
    (let [covered (fn [face]
                    (let [fr (face->rect face)
                          fa (* (:w fr) (:h fr))]
                      (if (pos? fa)
                        (min 1.0 (/ (reduce + 0.0 (map #(overlap-area fr %) bubbles)) fa))
                        0.0)))]
      (- 1.0 (apply max (map covered faces))))))

(defn face-presence-axis
  "期待 focal 数に対する検出顔数 → 0..1 | nil。`detected` は数 (カウント検出)
  でもボックス列でもよい。nil (検出不能 = no signal) / expected 0 (顔を期待
  しない panel) は nil — rubric 集約から除外され、罰しない。過検出 (背景の
  群衆顔) は正当なので 1.0 で頭打ち。"
  [expected detected]
  (let [n (cond (nil? detected) nil
                (number? detected) detected
                (sequential? detected) (count detected))]
    (when (and (some? n) (pos? (or expected 0)))
      (min 1.0 (/ n (double expected))))))

(defn reading-order-violations
  "パネル列 (読み順で与える。各 {:x :y :w :h}) の右→左・上→下 (日本語縦組み
  漫画の既定) に反する隣接遷移の数。annotated page の readingPath QA 用。
  遷移が「次のパネルの開始が前より下、または同じ帯で左」なら順方向とみなす。"
  [panels]
  (count
   (filter (fn [[a b]]
             (let [same-row? (< (Math/abs ^double (- (:y a) (:y b)))
                                (* 0.5 (min (:h a) (:h b))))]
               (if same-row?
                 ;; 同じ帯: 右→左が順方向 (b は a より左に始まるべき)
                 (>= (+ (:x b) (:w b)) (+ (:x a) (:w a)))
                 ;; 帯替わり: 下へ進むべき
                 (< (:y b) (:y a)))))
           (partition 2 1 panels))))
