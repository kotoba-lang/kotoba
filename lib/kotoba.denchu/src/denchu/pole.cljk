(ns denchu.pole
  "電柱（utility pole）の identity と、複数の観測源を1本の柱に束ねる純関数。

  この ns は **観測 (observation) と 柱 (pole) を厳密に区別する**。
  観測は「ある source が、ある座標に、ある種別の柱状物体を見た」という
  取り消し不能な事実であり、柱はそれらを空間的に束ねた導出物である。
  束ね方（半径・種別一致・信頼度）は全てこの ns の中で決まり、外から
  数値を持ち込めない — 同じ観測列からは常に同じ柱列が出る。

  **推測しないこと（設計上の不変条件）:**
  - 所有者は `operator` 相当のタグに実際の社名がある時だけ決まる。
    無ければ `:unknown`。座標や地域から推測しない。
  - 掲出可否 (`:pole/ad-eligible`) は常に `:unknown` から始まる。
    OSM にも Mapillary にも「この柱に広告を出せるか」は書かれていない —
    それを決めるのは柱の所有者と指定代理店であり、幾何情報ではない。
  - 信頼度は 0.95 を超えない。所有者確認を経ていない柱が 1.0 になる
    余地を残さないため。"
  (:require [kotoba.lang.text :as str]))

;; ── 座標 ────────────────────────────────────────────────────────────

(def ^:const earth-radius-m 6371008.8)

(defn- radians [deg] (* (/ (double deg) 180.0) Math/PI))

(defn haversine-m
  "2点間の大円距離 (m)。"
  [lat1 lon1 lat2 lon2]
  (let [dlat (radians (- (double lat2) (double lat1)))
        dlon (radians (- (double lon2) (double lon1)))
        a (+ (* (Math/sin (/ dlat 2)) (Math/sin (/ dlat 2)))
             (* (Math/cos (radians lat1)) (Math/cos (radians lat2))
                (Math/sin (/ dlon 2)) (Math/sin (/ dlon 2))))]
    (* earth-radius-m 2 (Math/atan2 (Math/sqrt a) (Math/sqrt (- 1 a))))))

(defn fixed6
  "小数第6位固定の文字列（約0.11m 相当の分解能）。`:pole/id` を
  プラットフォーム非依存にするため、浮動小数の既定印字に頼らない。"
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

(def observation-kinds
  "束ねる対象の柱種別。`:street-light` は電柱ではないが、OSM/Mapillary の
  誤分類が実在するので**捨てずに別 kind として保持**し、柱と混ぜない。"
  #{:utility-pole :pole :street-light})

(defn observation?
  [o]
  (and (map? o)
       (keyword? (:obs/source o))
       (string? (:obs/source-id o))
       (number? (:obs/lat o))
       (number? (:obs/lon o))
       (contains? observation-kinds (:obs/kind o))))

(defn invalid-observations
  "`observation?` を満たさない要素。空でなければ呼び出し側が止まる。
  黙って drop しない — 観測を落とすことは在庫を落とすこと。"
  [observations]
  (vec (remove observation? observations)))

;; ── 所有者 ──────────────────────────────────────────────────────────

(def operator-aliases
  "OSM `operator` タグ等に実際に現れる社名 → 所有者キーワード。
  ここに無い文字列は `:unknown` になる（推測しない）。送配電分社後の
  正式名と旧称の両方を持つ。"
  {"東京電力パワーグリッド" :tepco-pg
   "東京電力パワーグリッド株式会社" :tepco-pg
   "東京電力" :tepco-pg
   "TEPCO" :tepco-pg
   "東北電力ネットワーク" :tohoku-epco
   "東北電力" :tohoku-epco
   "中部電力パワーグリッド" :chuden-pg
   "中部電力" :chuden-pg
   "関西電力送配電" :kepco-t
   "関西電力" :kepco-t
   "中国電力ネットワーク" :energia-nw
   "中国電力" :energia-nw
   "四国電力送配電" :yonden-t
   "四国電力" :yonden-t
   "九州電力送配電" :kyuden-t
   "九州電力" :kyuden-t
   "北海道電力ネットワーク" :hepco-nw
   "北海道電力" :hepco-nw
   "北陸電力送配電" :rikuden-t
   "北陸電力" :rikuden-t
   "沖縄電力" :okiden
   "東日本電信電話" :ntt-east
   "東日本電信電話株式会社" :ntt-east
   "NTT東日本" :ntt-east
   "西日本電信電話" :ntt-west
   "西日本電信電話株式会社" :ntt-west
   "NTT西日本" :ntt-west})

(defn operator->owner
  "社名文字列 → 所有者キーワード。前方一致まで見るが、**部分一致で
  当てにいかない** — `nil`/未知は `:unknown` を返す。"
  [operator]
  (if (or (nil? operator) (str/blank? operator))
    :unknown
    (let [s (str/trim operator)]
      (or (get operator-aliases s)
          (some (fn [[alias owner]] (when (str/starts-with? s alias) owner))
                operator-aliases)
          :unknown))))

;; ── 信頼度 ──────────────────────────────────────────────────────────

(def ^:const max-confidence
  "所有者の確認を経ていない柱が到達できる上限。1.0 にしない。"
  0.95)

(def base-confidence
  "source × kind ごとの基礎点。OSM の `power=pole` は人手のマッピング、
  Mapillary の detection は自動抽出なので前者を高く置く。"
  {:osm       {:utility-pole 0.60 :pole 0.45 :street-light 0.30}
   :mapillary {:utility-pole 0.50 :pole 0.35 :street-light 0.25}})

(defn confidence
  "束ねた観測列 → 信頼度。加点は決定論的で、根拠は3つだけ:
  最良の基礎点 / 2 source 以上の一致 / 所有者証拠の有無。"
  [observations owner]
  (let [best (reduce max 0.0
                     (map (fn [o] (or (get-in base-confidence
                                              [(:obs/source o) (:obs/kind o)])
                                      0.2))
                          observations))
        sources (into #{} (map :obs/source) observations)
        multi (if (> (count sources) 1) 0.30 0.0)
        owned (if (not= owner :unknown) 0.05 0.0)]
    (min max-confidence (+ best multi owned))))

;; ── 束ね（fuse） ────────────────────────────────────────────────────

(defn- sort-key [o]
  [(:obs/lat o) (:obs/lon o) (name (:obs/source o)) (:obs/source-id o)])

(defn- centroid [observations]
  [(/ (reduce + (map :obs/lat observations)) (count observations))
   (/ (reduce + (map :obs/lon observations)) (count observations))])

(defn pole-id
  "座標から決まる安定 id。同じ座標からは常に同じ id が出る（実行順・
  ハッシュ順に依存しない）。identity ではなく discovery key である点は
  repo 名と同じ — 正本は観測の集合。"
  [lat lon]
  (str "denchu:" (fixed6 lat) "," (fixed6 lon)))

(defn- ->pole [observations]
  (let [[lat lon] (centroid observations)
        owner-obs (some (fn [o] (when-let [op (get-in o [:obs/tags "operator"])]
                                  (let [ow (operator->owner op)]
                                    (when (not= ow :unknown) [ow op]))))
                        (sort-by sort-key observations))
        [owner operator] (or owner-obs [:unknown nil])]
    {:pole/id (pole-id lat lon)
     :pole/lat lat
     :pole/lon lon
     :pole/kind (:obs/kind (first (sort-by sort-key observations)))
     :pole/owner owner
     :pole/owner-evidence (when operator (str "operator=" operator))
     :pole/sources (vec (sort (map (comp name :obs/source) observations)))
     :pole/observations (vec (sort-by sort-key observations))
     :pole/confidence (confidence observations owner)
     ;; 幾何情報からは決して導けない。代理店/所有者の回答が入るまで unknown。
     :pole/ad-eligible :unknown}))

(defn fuse
  "観測列 → 柱列。`radius-m` 以内かつ同一 kind の観測を1本に束ねる。
  入力を正規化順に並べてから貪欲に束ねるので、入力順に依存しない。

  戻り値は `{:poles [...] :rejected [...]}`。`:rejected` は
  `observation?` を満たさなかった入力で、**捨てずに返す**。"
  ([observations] (fuse observations {}))
  ([observations {:keys [radius-m] :or {radius-m 8.0}}]
   (let [bad (invalid-observations observations)
         good (sort-by sort-key (filter observation? observations))
         clusters (reduce
                   (fn [acc o]
                     (let [hit (some (fn [[idx c]]
                                       (let [[clat clon] (centroid c)]
                                         (when (and (= (:obs/kind (first c)) (:obs/kind o))
                                                    (<= (haversine-m clat clon
                                                                     (:obs/lat o) (:obs/lon o))
                                                        radius-m))
                                           idx)))
                                     (map-indexed vector acc))]
                       (if hit
                         (update acc hit conj o)
                         (conj acc [o]))))
                   []
                   good)]
     {:poles (vec (sort-by :pole/id (map ->pole clusters)))
      :rejected (vec bad)})))
