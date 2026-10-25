(ns okugai.site
  "掲出地点（site）の identity と、複数の観測源を 1 地点に束ねる純関数。
  `denchu.pole`（電柱専用）を全媒体に一般化したもの。

  **観測 (observation) と 地点 (site) を厳密に区別する。** 観測は「ある source が、
  ある座標に、ある媒体の物体を見た」という取り消し不能な事実、地点はそれらを
  空間的に束ねた導出物。束ね方（半径・媒体一致・信頼度）は全てこの ns の中で決まる。

  **推測しないこと（設計上の不変条件）:**
  - 所有者/設置者は `operator` 相当のタグに実際の名前がある時だけ決まる。無ければ
    `:unknown`。座標や地域から推測しない（媒体固有の候補導出は媒体 repo の仕事 ——
    電柱なら `denchu.area` が供給区域から候補を出す）。
  - 掲出可否 (`:site/ad-eligible`) は常に `:unknown` から始まる。OSM にも Mapillary
    にも『ここに広告を出せるか』は書かれていない。
  - 信頼度は 0.95 を超えない。所有者確認を経ていない地点が 1.0 になる余地を残さない。
  - **高さ・寸法を観測から導かない。** OSM/Mapillary は高さを持たないので、
    `:site/height-m` は常に nil から始まる —— 建築基準法88条の判定に直結するので、
    ここを推測で埋めると『確認申請不要』という嘘になる。"
  (:require [kotoba.lang.text :as str]
            [okugai.medium :as medium]))

;; ── 座標 ────────────────────────────────────────────────────────────

(def ^:const earth-radius-m 6371008.8)

(defn- radians [deg] (* (/ (double deg) 180.0) Math/PI))

(defn haversine-m
  [lat1 lon1 lat2 lon2]
  (let [dlat (radians (- (double lat2) (double lat1)))
        dlon (radians (- (double lon2) (double lon1)))
        a (+ (* (Math/sin (/ dlat 2)) (Math/sin (/ dlat 2)))
             (* (Math/cos (radians lat1)) (Math/cos (radians lat2))
                (Math/sin (/ dlon 2)) (Math/sin (/ dlon 2))))]
    (* earth-radius-m 2 (Math/atan2 (Math/sqrt a) (Math/sqrt (- 1 a))))))

(defn fixed6
  "小数第6位固定の文字列（約0.11m 相当）。id をプラットフォーム非依存にするため
  浮動小数の既定印字に頼らない。"
  [x]
  (let [scaled (Math/round (* (double x) 1e6))
        neg? (neg? scaled)
        a (if neg? (- scaled) scaled)
        i (quot a 1000000)
        f (rem a 1000000)
        fs (str f)
        pad (apply str (repeat (- 6 (count fs)) "0"))]
    (str (when neg? "-") i "." pad fs)))

;; ── 観測 ────────────────────────────────────────────────────────────

(defn observation?
  [o]
  (and (map? o)
       (keyword? (:obs/source o))
       (string? (:obs/source-id o))
       (number? (:obs/lat o))
       (number? (:obs/lon o))
       (medium/medium? (:obs/medium o))))

(defn invalid-observations
  "`observation?` を満たさない要素。黙って drop しない —— 観測を落とすことは
  在庫を落とすこと。"
  [observations]
  (vec (remove observation? observations)))

;; ── 信頼度 ──────────────────────────────────────────────────────────

(def ^:const max-confidence 0.95)

(def base-confidence
  "source ごとの基礎点。OSM は人手のマッピング、Mapillary の detection は自動抽出
  なので前者を高く置く。媒体ごとの差は付けない —— タグが付いている時点で
  マッパーが媒体を判断している。"
  {:osm 0.60 :mapillary 0.50})

(defn confidence
  [observations operator]
  (let [best (reduce max 0.0 (map #(get base-confidence (:obs/source %) 0.2) observations))
        sources (into #{} (map :obs/source) observations)
        multi (if (> (count sources) 1) 0.30 0.0)
        owned (if (and operator (not= operator :unknown)) 0.05 0.0)]
    (min max-confidence (+ best multi owned))))

;; ── 束ね（fuse） ────────────────────────────────────────────────────

(defn- sort-key [o]
  [(:obs/lat o) (:obs/lon o) (name (:obs/source o)) (:obs/source-id o)])

(defn- centroid [observations]
  [(/ (reduce + (map :obs/lat observations)) (count observations))
   (/ (reduce + (map :obs/lon observations)) (count observations))])

(defn site-id
  "座標 + 媒体から決まる安定 id。同じ入力からは常に同じ id（実行順・ハッシュ順に
  依存しない）。identity ではなく discovery key。"
  [medium-id lat lon]
  (str "okugai:" (name medium-id) ":" (fixed6 lat) "," (fixed6 lon)))

(defn- ->site [observations operator-resolver]
  (let [[lat lon] (centroid observations)
        sorted (sort-by sort-key observations)
        med (:obs/medium (first sorted))
        raw-op (some (fn [o] (let [v (get-in o [:obs/tags "operator"])]
                               (when (and (string? v) (seq (str/trim v))) (str/trim v))))
                     sorted)
        ;; 解決器には媒体も渡す —— 電柱の社名表と広告物の設置者名は別の体系で、
        ;; 電柱用の表を全媒体に当てると『株式会社アトレ』が :unknown に潰れる。
        operator (when raw-op (if operator-resolver (operator-resolver raw-op med) raw-op))]
    {:site/id (site-id med lat lon)
     :site/lat lat
     :site/lon lon
     :site/medium med
     :site/operator (or operator :unknown)
     :site/operator-raw raw-op
     :site/operator-evidence (when raw-op (str "operator=" raw-op))
     :site/sources (vec (sort (map (comp name :obs/source) observations)))
     :site/observations (vec sorted)
     :site/confidence (confidence observations operator)
     ;; 観測からは決して導けないもの
     :site/ad-eligible :unknown
     :site/height-m nil}))

(defn fuse
  "観測列 → 地点列。`radius-m` 以内かつ**同一媒体**の観測を 1 地点に束ねる。
  入力を正規化順に並べてから貪欲に束ねるので入力順に依存しない。

  `:operator-resolver` は `(fn [operator-string medium] -> 所有者)`（媒体 repo が
  渡す）。**媒体を受け取る**ので、自分が知らない媒体では生文字列を返せる。
  渡さなければ生文字列のまま。

  戻り値 `{:sites [...] :rejected [...]}`。`:rejected` は捨てずに返す。"
  ([observations] (fuse observations {}))
  ([observations {:keys [radius-m operator-resolver] :or {radius-m 8.0}}]
   (let [bad (invalid-observations observations)
         good (sort-by sort-key (filter observation? observations))
         clusters (reduce
                   (fn [acc o]
                     (let [hit (some (fn [[idx c]]
                                       (let [[clat clon] (centroid c)]
                                         (when (and (= (:obs/medium (first c)) (:obs/medium o))
                                                    (<= (haversine-m clat clon
                                                                     (:obs/lat o) (:obs/lon o))
                                                        radius-m))
                                           idx)))
                                     (map-indexed vector acc))]
                       (if hit (update acc hit conj o) (conj acc [o]))))
                   []
                   good)]
     {:sites (vec (sort-by :site/id (map #(->site % operator-resolver) clusters)))
      :rejected (vec bad)})))

(defn by-medium
  "地点列 → 媒体ごとの件数。カバレッジ申告に使う。"
  [sites]
  (frequencies (map (comp name :site/medium) sites)))
