#!/usr/bin/env kbb
;; edn-datomize.bb — EDN → Datomic/Datascript tx-data 変換ツール（org-iso-jpeg 用に adapt）。
;; 出自: com-junkawasaki/root superproject の manifest/edn-datomize.bb (Phase 1/2 実装)。
;; schema-path をこの子repo のルート（manifest/ が無いため repo root 直下）に adapt。
;; 追加: 既に idiomatic に名前空間付きキー（:actor/*, :cell/* 等）を持つファイル用の
;; namespace-preserving モード（wrap-map-preserve!）— 既存の名前空間はそのまま保持し、
;; bare キーのみ ns-name で prefix する（Phase 2 の kotoba-lang/security・
;; gftdcojp/net-kotobase pilot と同型）。
;;
;; 使い方:
;;   bb edn-datomize.bb wrap-map <path> <ns>          — map 1個、キー全部に ns を付与
;;   bb edn-datomize.bb wrap-map-preserve <path> <ns>  — map 1個、bare キーだけ ns を付与
;;   bb edn-datomize.bb wrap-vec-preserve <path>       — vector-of-map、各 map は名前空間済み前提
;;                                                        (:db/id を振って blob 化するだけ)

(require '[clojure.edn :as edn]
         '[clojure.java.io :as io]
         '[clojure.java.shell :as shell]
         '[clojure.string :as str])

(def root (str/trim (:out (shell/sh "git" "rev-parse" "--show-toplevel"))))

(defn schema-path [] (io/file root "schema.edn"))

(defn slurp-edn [path] (edn/read-string (slurp path)))

(defn already-tx-data?
  [content]
  (and (vector? content) (seq content) (map? (first content)) (contains? (first content) :db/id)))

(defn classify
  [v]
  (cond
    (string? v)  {:type :db.type/string  :card :db.cardinality/one}
    (boolean? v) {:type :db.type/boolean :card :db.cardinality/one}
    (integer? v) {:type :db.type/long    :card :db.cardinality/one}
    (double? v)  {:type :db.type/double  :card :db.cardinality/one}
    (keyword? v) {:type :db.type/keyword :card :db.cardinality/one}
    (nil? v)     {:type :db.type/string  :card :db.cardinality/one}
    (and (coll? v) (empty? v))
    {:type :db.type/string :card :db.cardinality/many}
    (and (coll? v) (every? string? v))  {:type :db.type/string  :card :db.cardinality/many}
    (and (coll? v) (every? keyword? v)) {:type :db.type/keyword :card :db.cardinality/many}
    (and (coll? v) (every? integer? v)) {:type :db.type/long    :card :db.cardinality/many}
    :else {:type :db.type/string :card :db.cardinality/one :blob true}))

(defn attr-value [v]
  (let [{:keys [blob]} (classify v)]
    (if blob (pr-str v) v)))

(defn namespaced-key [ns-name k]
  (keyword ns-name (name k)))

(defn preserve-key
  "既に名前空間付きキーはそのまま、bare キーは ns-name で prefix する。"
  [ns-name k]
  (if (namespace k) k (namespaced-key ns-name k)))

(defn entity-from-map
  [content ns-name]
  (into {:db/id -1}
        (map (fn [[k v]] [(namespaced-key ns-name k) (attr-value v)]))
        content))

(defn entity-from-map-preserve
  [content ns-name]
  (into {:db/id -1}
        (map (fn [[k v]] [(preserve-key ns-name k) (attr-value v)]))
        content))

(defn schema-attrs
  [content key-fn ns-name]
  (for [[k v] content]
    (let [{:keys [type card]} (classify v)]
      {:db/ident (key-fn ns-name k)
       :db/valueType type
       :db/cardinality card})))

(defn load-schema []
  (let [f (schema-path)]
    (if (.exists f) (slurp-edn f) [])))

(defn merge-schema! [new-attrs]
  (let [existing (load-schema)
        by-ident (into {} (map (juxt :db/ident identity)) existing)
        merged-by-ident (reduce (fn [acc {:keys [db/ident] :as attr}]
                                   (if (contains? acc ident) acc (assoc acc ident attr)))
                                 by-ident
                                 new-attrs)
        merged (vec (sort-by (comp str :db/ident) (vals merged-by-ident)))]
    (spit (schema-path) (str ";; schema.edn — Datomic/Datascript 互換スキーマ定義（自動生成 by edn-datomize.bb）\n"
                              ";; :db/ident 属性定義のリスト。Datomic 固有キー(:db.install/_attribute 等)は使わない。\n"
                              ";; 手編集禁止 — 再生成すると上書きされる。\n"
                              ";; 注: kotoba/schema.edn（手書きの正本スキーマ）とは別物 — こちらは\n"
                              ";; edn-datomize.bb が変換した各種 .edn ファイル（actor/cell/lex 等の\n"
                              ";; メタデータ）専用の付随スキーマ。\n\n"
                              (pr-str merged)
                              "\n"))
    merged))

(defn wrap-map! [rel-path ns-name]
  (let [f (io/file root rel-path)
        content (slurp-edn f)]
    (if (already-tx-data? content)
      (println "skip (already tx-data):" rel-path)
      (let [entity (entity-from-map content ns-name)
            attrs (schema-attrs content namespaced-key ns-name)]
        (spit f (pr-str [entity]))
        (merge-schema! attrs)
        (println "wrapped" rel-path "->" (count entity) "attrs, ns=" ns-name)))))

(defn wrap-map-preserve! [rel-path ns-name]
  (let [f (io/file root rel-path)
        content (slurp-edn f)]
    (if (already-tx-data? content)
      (println "skip (already tx-data):" rel-path)
      (let [entity (entity-from-map-preserve content ns-name)
            attrs (schema-attrs content preserve-key ns-name)]
        (spit f (pr-str [entity]))
        (merge-schema! attrs)
        (println "wrapped(preserve)" rel-path "->" (count entity) "attrs, ns=" ns-name)))))

(defn -main [& args]
  (let [[mode a b] args]
    (case mode
      "wrap-map"          (wrap-map! a b)
      "wrap-map-preserve" (wrap-map-preserve! a b)
      (do (println "usage: bb edn-datomize.bb [wrap-map <path> <ns> | wrap-map-preserve <path> <ns>]")
          (System/exit 1)))))

(apply -main *command-line-args*)
