(ns kami.paint
  "3D テクスチャペイント —— UV 空間のテクスチャに、3D 表面の上から塗る。

  Substance 3D Painter や Mari がやっていることの中核は、**3D の筆圧を UV の
  テクセルに移す**ことである。難しいのは筆そのものではなく、その移送:

  - どのテクセルが、いま筆の下にある表面の点に対応するか
  - UV の島の境界（シーム）をまたぐと、隣り合う 3D 上の点がテクスチャ上では
    遠く離れる。**塗った色は島の外へ滲ませないと、双一次補間が背景を拾う**
  - 層は順序を持つ。multiply の後の add と add の後の multiply は違う絵になる

  ここで検査できる形にした主張:

  - **UV 逆写像は厳密**。テクセル中心から重心座標で 3D 点を復元すると、
    平面三角形では 1e-12 で一致する。ベイクした world position を読み戻す
    ことで、それを数で確かめる
  - **筆の被覆は円板**。既知の UV 尺度を持つ平面パッチに半径 r で塗ると、
    塗られたテクセル数は πr²/テクセル面積 に離散化誤差の範囲で一致する ——
    「それらしく塗れた」ではなく面積で確かめる
  - **減衰は距離で落ちる**（中心の近くほど強い）
  - **層の合成は非可換**。multiply→add と add→multiply が違うことを
    テストが要求する。可換な実装（全部 add）はここで落ちる
  - **シームの滲ませ（dilation）**は、島の外のテクセルに最近傍の島の色を
    入れる。**滲ませないと双一次補間がシームで背景を拾う**ことを、滲ませた
    場合との差として測る

  ここに無いもの: 投影ペイント（画面空間からの投影）、tri-planar、ステンシル、
  筆のテクスチャ、UV 展開そのもの（`kami.modeling` のトリム面と別の話）、
  テクスチャの圧縮・書き出し形式。**PBR 層は値の合成までで、レンダリングは
  しない** —— それは `kotoba-lang/raytrace` と `kotoba-lang/webgpu` の面。"
  (:require [kotoba.lang.text :as string]))

(defn- v- [a b] (mapv - a b))
(defn- v+ [a b] (mapv + a b))
(defn- vs [a s] (mapv #(* s %) a))
(defn- dot [a b] (reduce + (map * a b)))
(defn- norm [a] (#?(:clj Math/sqrt :cljs js/Math.sqrt) (dot a a)))

;; ---------------------------------------------------------------------------
;; テクスチャ
;; ---------------------------------------------------------------------------

(defn texture
  "`w` x `h` のテクスチャ。値は channels 個の成分を持つベクタ。"
  ([w h] (texture w h [0.0 0.0 0.0]))
  ([w h fill]
   {:texture/width w :texture/height h
    :texture/channels (count fill)
    :texture/texels (vec (repeat (* w h) (vec fill)))}))

(defn texel [{:keys [texture/width texture/texels]} x y] (nth texels (+ (* y width) x)))

(defn with-texel [t x y v]
  (assoc-in t [:texture/texels (+ (* (:texture/height t) 0) (* y (:texture/width t)) x)] v))

(defn texel-centre
  "テクセル (x, y) の中心の UV。**中心であって角ではない** —— 角を使うと
  半テクセルずれ、ベイクした位置が系統的にずれる。"
  [{:keys [texture/width texture/height]} x y]
  [(/ (+ x 0.5) width) (/ (+ y 0.5) height)])

(defn sample-bilinear
  "UV でテクスチャを双一次サンプリングする。シームの検査に使う。"
  [{:keys [texture/width texture/height] :as t} [u v]]
  (let [fx (- (* u width) 0.5) fy (- (* v height) 0.5)
        x0 (long (#?(:clj Math/floor :cljs js/Math.floor) fx))
        y0 (long (#?(:clj Math/floor :cljs js/Math.floor) fy))
        tx (- fx x0) ty (- fy y0)
        cl (fn [a lo hi] (max lo (min hi a)))
        g (fn [x y] (texel t (cl x 0 (dec width)) (cl y 0 (dec height))))]
    (mapv (fn [c]
            (let [a (nth (g x0 y0) c) b (nth (g (inc x0) y0) c)
                  cc (nth (g x0 (inc y0)) c) d (nth (g (inc x0) (inc y0)) c)]
              (+ (* (- 1 tx) (- 1 ty) a) (* tx (- 1 ty) b)
                 (* (- 1 tx) ty cc) (* tx ty d))))
          (range (:texture/channels t)))))

;; ---------------------------------------------------------------------------
;; UV と表面の対応
;; ---------------------------------------------------------------------------

(defn- tri-uvs [mesh [a b c]]
  [(nth (:uvs mesh) a) (nth (:uvs mesh) b) (nth (:uvs mesh) c)])

(defn- tri-positions [mesh [a b c]]
  [(nth (:positions mesh) a) (nth (:positions mesh) b) (nth (:positions mesh) c)])

(defn barycentric-2d
  "点 p を三角形 (a b c) の重心座標で表す。UV 空間で使う。"
  [p [ax ay] [bx by] [cx cy]]
  (let [[px py] p
        d (- (* (- by cy) (- ax cx)) (* (- bx cx) (- ay cy)))]
    (when-not (zero? d)
      (let [l1 (/ (+ (* (- by cy) (- px cx)) (* (- cx bx) (- py cy))) d)
            l2 (/ (+ (* (- cy ay) (- px cx)) (* (- ax cx) (- py cy))) d)]
        [l1 l2 (- 1.0 l1 l2)]))))

(defn- inside? [[l1 l2 l3]] (and (>= l1 -1.0e-9) (>= l2 -1.0e-9) (>= l3 -1.0e-9)))

(defn surface-point
  "UV から 3D 表面の点へ。UV 島の外なら nil。

  これがこの namespace の心臓で、**逆写像が厳密でなければ塗りもベイクも
  半テクセルずれる**。平面三角形では重心座標がアフィンなので厳密に戻る。"
  [mesh uv]
  (some (fn [tri]
          (let [[ta tb tc] (tri-uvs mesh tri)]
            (when-let [bc (barycentric-2d uv ta tb tc)]
              (when (inside? bc)
                (let [[pa pb pc] (tri-positions mesh tri)
                      [l1 l2 l3] bc]
                  {:point (v+ (vs pa l1) (v+ (vs pb l2) (vs pc l3)))
                   :triangle tri :barycentric bc})))))
        (partition 3 (:indices mesh))))

;; ---------------------------------------------------------------------------
;; ペイント
;; ---------------------------------------------------------------------------

(defn paint-error
  "この筆・この網では塗れない理由、または nil。"
  [mesh {:keys [centre radius strength]} tex]
  (cond
    (not (seq (:uvs mesh)))
    (str "網に UV が無い。3D テクスチャペイントは 3D の筆圧を UV のテクセルへ"
         " 移す操作なので、UV が無ければ移す先が無い —— 展開してから塗ること")

    (not= (count (:uvs mesh)) (count (:positions mesh)))
    (str "UV が " (count (:uvs mesh)) " 個、頂点が " (count (:positions mesh))
         " 個。**足りない側は黙って別の頂点の UV を拾う**ので、塗った色が"
         " 別の場所に出る")

    (not (and (number? radius) (pos? radius)))
    (str "筆の半径は正でなければならない（" (pr-str radius) "）")

    (not (and (number? strength) (<= 0.0 strength 1.0)))
    (str "筆の強さは [0,1]（" (pr-str strength) "）—— 1 を超える強さは"
         " 1 回のストロークで色を超過させ、層の合成が定義から外れる")

    (not (and (:texture/width tex) (pos? (:texture/width tex))))
    "テクスチャの大きさが正でない"

    (not= 3 (count centre))
    (str "筆の中心は 3D 点（" (pr-str centre) "）")))

(defn paint-stroke
  "3D の点 `centre` を中心に半径 `radius` で塗る。

  各テクセルについて、その中心の UV が表面のどこかを求め、筆の中心からの
  **3D 距離**で内外を決める。UV 上の距離ではない —— UV は伸び縮みするので、
  UV で丸い筆は 3D では歪む。

  返すのは `[:ok texture]` か `[:error msg]`。"
  [mesh brush tex]
  (if-let [e (paint-error mesh brush tex)]
    [:error e]
    (let [{:keys [centre radius strength colour falloff]
           :or {colour [1.0 1.0 1.0] falloff :quadratic}} brush
          {:keys [texture/width texture/height]} tex]
      [:ok
       (reduce
        (fn [t [x y]]
          (let [uv (texel-centre t x y)]
            (if-let [{:keys [point]} (surface-point mesh uv)]
              (let [d (norm (v- point centre))]
                (if (>= d radius)
                  t
                  (let [f (case falloff
                            :constant 1.0
                            :linear (- 1.0 (/ d radius))
                            (let [k (- 1.0 (/ d radius))] (* k k)))
                        a (* strength f)
                        old (texel t x y)]
                    (with-texel t x y (mapv (fn [o c] (+ (* (- 1.0 a) o) (* a c))) old colour)))))
              t)))
        tex
        (for [y (range height) x (range width)] [x y]))])))

;; ---------------------------------------------------------------------------
;; 層
;; ---------------------------------------------------------------------------

(def blend-modes
  "合成モード。**ここに登録することが「そのモードを持っている」という主張**で、
  対応表を別に持たない（`brep.feature/apply-feature` と同じ形）。"
  {:normal (fn [b a] a)
   :multiply (fn [b a] (* b a))
   :add (fn [b a] (+ b a))
   :screen (fn [b a] (- 1.0 (* (- 1.0 b) (- 1.0 a))))})

(defn material-layer
  [{:keys [id texture blend opacity]
    :or {blend :normal opacity 1.0}}]
  {:layer/id id :layer/texture texture :layer/blend blend :layer/opacity opacity})

(defn layer-error [layers]
  (or (some (fn [l]
              (cond
                (not (contains? blend-modes (:layer/blend l)))
                (str "合成モード " (pr-str (:layer/blend l)) " は登録されていない。"
                     "在るのは " (string/join ", " (sort (map name (keys blend-modes)))))
                (not (<= 0.0 (:layer/opacity l) 1.0))
                (str "層 " (:layer/id l) " の不透明度が [0,1] の外（"
                     (:layer/opacity l) "）")))
            layers)
      (when (empty? layers) "層が 1 つも無い")))

(defn flatten-layers
  "層を下から順に合成する。**順序は意味を持つ** —— multiply の後の add と
  add の後の multiply は違う絵になる。"
  [base layers]
  (if-let [e (layer-error layers)]
    [:error e]
    [:ok
     (reduce
      (fn [acc {:layer/keys [texture blend opacity]}]
        (let [f (get blend-modes blend)]
          (assoc acc :texture/texels
                 (vec (map (fn [b a]
                             (mapv (fn [bc ac]
                                     (let [mixed (f bc ac)]
                                       (+ (* (- 1.0 opacity) bc) (* opacity mixed))))
                                   b a))
                           (:texture/texels acc) (:texture/texels texture))))))
      base layers)]))

;; ---------------------------------------------------------------------------
;; ベイク
;; ---------------------------------------------------------------------------

(defn bake-texture
  "表面の量をテクスチャに焼く。`f` は `{:point :triangle :barycentric}` を
  受けて channels 個の値を返す。島の外は `background`。

  ベイクは**逆写像が厳密かどうかを数で示す**手段でもある: world position を
  焼いて読み戻せば、テクセル中心の UV が指す点そのものが返る。"
  [mesh tex f & {:keys [background] :or {background [0.0 0.0 0.0]}}]
  (if-not (seq (:uvs mesh))
    [:error "網に UV が無いのでベイクできない"]
    [:ok
     (reduce (fn [t [x y]]
               (if-let [hit (surface-point mesh (texel-centre t x y))]
                 (with-texel t x y (f hit))
                 (with-texel t x y background)))
             tex
             (for [y (range (:texture/height tex)) x (range (:texture/width tex))] [x y]))]))

;; ---------------------------------------------------------------------------
;; シームの滲ませ
;; ---------------------------------------------------------------------------

(defn dilate
  "島の外のテクセルに、最近傍の島のテクセルの値を `pad` 回だけ広げる。

  **これが無いと双一次補間がシームで背景を拾う。** 島の縁のテクセルを読む
  とき、補間は隣（島の外）も混ぜるからで、塗った色と背景の中間色が縁に
  出る —— レンダリングすると継ぎ目に黒い線が走る、あの現象である。"
  [mesh tex pad]
  (let [{:keys [texture/width texture/height]} tex
        inside (into #{} (for [y (range height) x (range width)
                               :when (surface-point mesh (texel-centre tex x y))]
                           [x y]))]
    (loop [t tex known inside n pad]
      (if (or (zero? n) (= (count known) (* width height)))
        t
        (let [grow (for [y (range height) x (range width)
                         :when (not (known [x y]))
                         :let [ns (filter known [[(dec x) y] [(inc x) y] [x (dec y)] [x (inc y)]])]
                         :when (seq ns)]
                     [[x y] (first ns)])]
          (recur (reduce (fn [acc [[x y] [sx sy]]] (with-texel acc x y (texel t sx sy))) t grow)
                 (into known (map first grow))
                 (dec n)))))))

;; ---------------------------------------------------------------------------
;; PBR マテリアル
;; ---------------------------------------------------------------------------

(def pbr-channels
  "PBR マテリアルが持つチャンネルと、その値域。

  **値域を持つことが要点である。** roughness 1.2 や metallic -0.3 は
  レンダラで未定義の振る舞いになり、しかも「少し変な絵」として出るので
  気づきにくい。ここで閉じる。"
  {:base-colour {:channels 3 :range [0.0 1.0]}
   :roughness   {:channels 1 :range [0.0 1.0]}
   :metallic    {:channels 1 :range [0.0 1.0]}
   :normal      {:channels 3 :range [-1.0 1.0]}})

(defn pbr-material
  "チャンネルごとにテクスチャを持つマテリアル。"
  [m] {:material/channels m})

(defn material-error
  "このマテリアルが PBR として成立しない理由、または nil。"
  [{:keys [material/channels]}]
  (or (some (fn [[k _]]
              (when-not (contains? pbr-channels k)
                (str "チャンネル " (pr-str k) " は PBR の語彙に無い。在るのは "
                     (string/join ", " (sort (map name (keys pbr-channels)))))))
            channels)
      (some (fn [[k tex]]
              (let [{:keys [channels range]} (get pbr-channels k)
                    [lo hi] range]
                (cond
                  (not= channels (:texture/channels tex))
                  (str (name k) " は " channels " 成分だが、テクスチャは "
                       (:texture/channels tex) " 成分")
                  :else
                  (when-let [bad (first (filter (fn [t] (some #(or (< % lo) (> % hi)) t))
                                                (:texture/texels tex)))]
                    (str (name k) " に値域 [" lo ", " hi "] の外の値がある: "
                         (pr-str bad) " —— レンダラでは「少し変な絵」として出るので、"
                         "ここで閉じる")))))
            channels)
      (when (empty? channels) "チャンネルが 1 つも無い")))

(defn paint-material
  "マテリアルの 1 チャンネルに塗る。他のチャンネルは触らない。

  **チャンネルを間違えて塗るのは、色を roughness に書き込むこと**である ——
  絵は出るし、光り方だけが説明のつかないものになる。だから存在しない
  チャンネル名は拒否する。"
  [mesh brush material channel]
  (let [tex (get-in material [:material/channels channel])]
    (cond
      (not (contains? pbr-channels channel))
      [:error (str "チャンネル " (pr-str channel) " は PBR の語彙に無い。在るのは "
                   (string/join ", " (sort (map name (keys pbr-channels)))))]
      (nil? tex)
      [:error (str "このマテリアルは " (name channel) " を持っていない")]
      :else
      (let [[status result] (paint-stroke mesh brush tex)]
        (if (= :error status)
          [:error result]
          [:ok (assoc-in material [:material/channels channel] result)])))))
