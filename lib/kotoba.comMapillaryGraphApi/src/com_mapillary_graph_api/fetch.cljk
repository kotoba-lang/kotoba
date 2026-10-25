(ns com-mapillary-graph-api.fetch
  "Mapillary Graph API への I/O（nbb / Node）。純粋部分は `core`。

  token は **環境変数からしか読まない**（`MAPILLARY_ACCESS_TOKEN`）。
  コードにも設定ファイルにも書かない。token が無いときは投げる — 空文字で
  叩いて 401 を『データが無い』と誤読させないため。"
  (:require [com-mapillary-graph-api.core :as core]))

(defn access-token
  "環境変数から token を読む。無ければ明示的に落とす。"
  []
  (let [t (some-> js/process .-env .-MAPILLARY_ACCESS_TOKEN)]
    (when (or (nil? t) (= "" t))
      (throw (ex-info (str "MAPILLARY_ACCESS_TOKEN is not set. "
                           "Mapillary は認証必須で、token 無しの応答を『柱が無い』と読んではならない。")
                      {})))
    t))

(defn- query-string [params]
  (->> params
       (map (fn [[k v]] (str (js/encodeURIComponent k) "=" (js/encodeURIComponent v))))
       (interpose "&")
       (apply str)))

(defn- get-json
  [{:keys [url query-params]} token]
  (-> (js/fetch (str url "?" (query-string query-params))
                #js {:method "GET"
                     :headers (clj->js (core/authorization-header token))})
      (.then (fn [res]
               (if (.-ok res)
                 (.then (.json res) (fn [j] (js->clj j)))
                 (throw (ex-info "mapillary request failed"
                                 {:status (.-status res) :url url})))))))

(defn fetch-poles-tile
  "0.01 度以下の 1 タイル分の柱観測。"
  ([bbox] (fetch-poles-tile bbox {}))
  ([bbox {:keys [token] :as opts}]
   (let [t (or token (access-token))]
     (-> (get-json (core/map-features-request
                    bbox (merge {:object-values core/pole-object-values}
                                (dissoc opts :token)))
                   t)
         (.then core/parse-map-features)))))

(defn fetch-poles
  "任意サイズの bbox。API 制約に合わせてタイル分割し、直列に舐めて束ねる
  （並列に叩かない — 共有 API に対する節度）。"
  ([bbox] (fetch-poles bbox {}))
  ([bbox opts]
   (let [tiles (core/split-bbox bbox)]
     (reduce (fn [p tile]
               (.then p (fn [acc]
                          (.then (fetch-poles-tile tile opts)
                                 (fn [r]
                                   (-> acc
                                       (update :observations into (:observations r))
                                       (update :raw-count + (:raw-count r))
                                       (update :unclassified + (:unclassified r))
                                       (update :tiles inc)))))))
             (js/Promise.resolve {:observations [] :raw-count 0 :unclassified 0 :tiles 0})
             tiles))))
