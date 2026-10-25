(ns com-mapillary-graph-api.core
  "Mapillary Graph API v4 に対する **純粋な** リクエスト組み立てと応答正規化。

  Mapillary はストリートレベル画像とその上の物体検出（Mapillary Vistas 由来の
  taxonomy）を公開しており、`map_features` は複数画像から三角測量された
  『地物』を座標付きで返す。電柱広告の在庫候補探索から見ると、これは
  **写真から柱を特定する経路**そのものである。

  API 側の実測制約（2026-08-04 時点の公式ドキュメント）:
  - host は `https://graph.mapillary.com`
  - 認証は `?access_token=` または `Authorization: OAuth <token>`
  - **bbox は 0.01 度四方より小さくなければならない** → 広い面を引くには
    タイル分割が必須（`split-bbox`）
  - `limit` は最大 2000
  - `map_features` は `object_values` で絞り込める

  この ns は token を保持しない。token は呼び出し側が capability として渡す
  （鍵をコードに焼かない）。"
  (:require [kotoba.lang.text :as str]))

(def base-url "https://graph.mapillary.com")

(def ^:const max-bbox-degrees
  "API 制約: bbox は 0.01 度四方より小さいこと。"
  0.01)

(def ^:const max-limit 2000)

(def object-values
  "この repo が扱う `object_value` の実文字列（公式 taxonomy から確認）。
  推測した文字列を混ぜない — 存在しない値で絞ると空応答が『柱が無い』に
  見えてしまう。"
  {:utility-pole "object--support--utility-pole"
   :pole "object--support--pole"
   :traffic-sign-frame "object--support--traffic-sign-frame"
   :street-light "object--street-light"
   :banner "object--banner"
   :sign-advertisement "object--sign--advertisement"
   :sign-store "object--sign--store"
   :sign-information "object--sign--information"})

(def pole-object-values
  "柱そのもの。電柱の候補になるのはここ。"
  [(object-values :utility-pole) (object-values :pole)])

(def ad-object-values
  "既に何かが掲出されている面。『その柱に広告が実在するか』の観測に使う
  （在庫の空きではない — 空きは代理店しか知らない）。"
  [(object-values :banner) (object-values :sign-advertisement)
   (object-values :sign-store) (object-values :sign-information)])

(def object-value->kind
  "Mapillary の値 → `denchu.pole` の kind。逆写像を推測で作らない。"
  {"object--support--utility-pole" :utility-pole
   "object--support--pole" :pole
   "object--street-light" :street-light})

;; ── bbox ────────────────────────────────────────────────────────────

(defn bbox-str
  "Mapillary の bbox は west,south,east,north（GeoJSON 順）。Overpass とは
  順序が違うので、ここで一度だけ変換する。"
  [{:keys [west south east north]}]
  (str west "," south "," east "," north))

(defn bbox-within-limit?
  [{:keys [west south east north]}]
  (and (< (- east west) max-bbox-degrees)
       (< (- north south) max-bbox-degrees)))

(defn split-bbox
  "bbox を API 制約以下のタイルに割る。決定論的（南西から行優先）。
  `step` は既定 0.009 度 — 0.01 ちょうどにすると浮動小数の丸めで境界を
  超えることがあるため、わずかに小さく取る。"
  ([bbox] (split-bbox bbox 0.009))
  ([{:keys [west south east north]} step]
   (when-not (and (< west east) (< south north))
     (throw (ex-info "invalid bbox" {:west west :south south :east east :north north})))
   (vec
    (for [s (range south north step)
          w (range west east step)]
      {:west w
       :south s
       :east (min east (+ w step))
       :north (min north (+ s step))}))))

;; ── requests ────────────────────────────────────────────────────────

(def default-map-feature-fields
  ["id" "object_value" "geometry" "first_seen_at" "last_seen_at"])

(defn map-features-request
  "`{:url :query-params}`。token は `:access-token` で渡すか、渡さずに
  `authorization-header` を使う（後者を推奨 — URL にトークンを残さない）。"
  [bbox {:keys [object-values fields limit access-token]
         :or {fields default-map-feature-fields limit 2000}}]
  (when-not (bbox-within-limit? bbox)
    (throw (ex-info "bbox exceeds Mapillary's 0.01 degree limit; use split-bbox"
                    {:bbox bbox :max-bbox-degrees max-bbox-degrees})))
  (when (> limit max-limit)
    (throw (ex-info "limit exceeds API maximum" {:limit limit :max max-limit})))
  {:url (str base-url "/map_features")
   :query-params (cond-> {"bbox" (bbox-str bbox)
                          "fields" (str/join "," fields)
                          "limit" (str limit)}
                   (seq object-values) (assoc "object_values" (str/join "," object-values))
                   access-token (assoc "access_token" access-token))})

(defn images-request
  [bbox {:keys [fields limit access-token]
         :or {fields ["id" "geometry" "captured_at" "compass_angle" "thumb_1024_url"]
              limit 2000}}]
  (when-not (bbox-within-limit? bbox)
    (throw (ex-info "bbox exceeds Mapillary's 0.01 degree limit; use split-bbox"
                    {:bbox bbox})))
  {:url (str base-url "/images")
   :query-params (cond-> {"bbox" (bbox-str bbox)
                          "fields" (str/join "," fields)
                          "limit" (str limit)}
                   access-token (assoc "access_token" access-token))})

(defn detections-request
  "1 枚の画像、または 1 つの map feature に紐づく検出。
  `kind` は `:image` か `:map-feature`。"
  [kind id {:keys [fields access-token]
            :or {fields ["id" "value" "geometry" "created_at"]}}]
  (when-not (#{:image :map-feature} kind)
    (throw (ex-info "unknown detections subject" {:kind kind})))
  {:url (str base-url "/" id "/detections")
   :query-params (cond-> {"fields" (str/join "," fields)}
                   access-token (assoc "access_token" access-token))})

(defn authorization-header
  "URL ではなくヘッダで token を送る。access token を query string に置くと
  ログ・履歴・Referer に残るため、こちらを既定にする。"
  [token]
  (when (or (nil? token) (str/blank? token))
    (throw (ex-info "missing Mapillary access token" {})))
  {"Authorization" (str "OAuth " token)})

;; ── responses ───────────────────────────────────────────────────────

(defn- point-coords
  "GeoJSON Point → [lon lat]。Point 以外は nil（面や線は柱の観測にしない）。"
  [geometry]
  (let [g (if (string? geometry) nil geometry)]
    (when (and g (= "Point" (get g "type")))
      (let [[lon lat] (get g "coordinates")]
        (when (and (number? lon) (number? lat)) [lon lat])))))

(defn map-feature->observation
  "map feature → `denchu.pole` が受け取る観測。既知の object_value かつ
  Point 幾何を持つものだけ。それ以外は nil（呼び出し側が数える）。"
  [feature]
  (let [ov (get feature "object_value")
        kind (get object-value->kind ov)
        [lon lat] (point-coords (get feature "geometry"))
        id (get feature "id")]
    (when (and kind lon lat id)
      {:obs/source :mapillary
       :obs/source-id (str id)
       :obs/lat lat
       :obs/lon lon
       :obs/kind kind
       :obs/tags (cond-> {"object_value" ov}
                   (get feature "first_seen_at") (assoc "first_seen_at" (get feature "first_seen_at"))
                   (get feature "last_seen_at") (assoc "last_seen_at" (get feature "last_seen_at")))
       :obs/evidence-url (str "https://www.mapillary.com/app/?focus=map&mapFeature=" id)})))

(defn parse-map-features
  "`{\"data\" [...]}` → `{:observations [...] :raw-count n :unclassified n}`。
  Overpass 側と同じく、読めなかった件数を必ず返す。"
  [json]
  (let [data (get json "data" [])
        obs (keep map-feature->observation data)]
    {:observations (vec obs)
     :raw-count (count data)
     :unclassified (- (count data) (count obs))}))

(defn ad-presence
  "広告系 object_value の検出を『その座標に掲出物が実在した』観測として返す。
  **空き在庫の証拠ではない** — 掲出物が写っていることは、そこが売られている
  ことも、空いていることも意味しない。"
  [json]
  (let [data (get json "data" [])
        ads (filter (fn [f] (some #{(get f "object_value")} ad-object-values)) data)]
    (vec (keep (fn [f]
                 (when-let [[lon lat] (point-coords (get f "geometry"))]
                   {:ad/source :mapillary
                    :ad/source-id (str (get f "id"))
                    :ad/object-value (get f "object_value")
                    :ad/lat lat :ad/lon lon
                    :ad/note "掲出物が観測されただけ。販売可否・空きの証拠ではない。"}))
               ads))))
