#!/usr/bin/env kbb
;; edn-datomize.bb — EDN -> Datomic/Datascript tx-data 変換ツール
;; (adapted from com-junkawasaki/root's manifest/edn-datomize.bb, commit
;; a2090e87a730, for use inside a single child repo's own worktree — schema
;; lives at this repo's own root, not manifest/).
;;
;; 「datomic/datascript query 可能」の定義: ファイルのトップレベルが
;; (d/transact conn (edn/read-string (slurp file))) にそのまま渡せる
;; tx-data ベクタ（entity-map のベクタ、各 map は :db/id を持つ）であること。
;;
;; このリポジトリの resources/kotoba/sarutahiko-factory/*.edn は元々
;; :factory/* :clashes/* :construction-order/* :prod-order/* :robots/*
;; のように idiomatic に名前空間付きキーを使っているため、汎用 wrap-map!
;; （キーに新しい ns を機械的に前置する）ではなく、既存の名前空間を
;; 保存する preserve-ns モードを使う。値が Datomic の scalar valueType
;; （string/long/double/boolean/keyword、またはそれらの homogeneous な
;; collection）に収まらないもの（入れ子 map、map を含む vector 等）は
;; pr-str した文字列として保持する（valueType=string の "blob" 属性）。

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
    (and (coll? v) (every? double? v))  {:type :db.type/double  :card :db.cardinality/many}
    :else {:type :db.type/string :card :db.cardinality/one :blob true}))

(defn attr-value [v]
  (let [{:keys [blob]} (classify v)]
    (if blob (pr-str v) v)))

(defn namespaced-key [ns-name k]
  (keyword ns-name (name k)))

(defn entity-from-map
  "汎用モード: トップレベル map の各キーに ns-name の名前空間を付ける。"
  [content ns-name]
  (into {:db/id -1}
        (map (fn [[k v]] [(namespaced-key ns-name k) (attr-value v)]))
        content))

(defn entity-from-map-preserve-ns
  "preserve-ns モード: 既に名前空間付きのキーはそのまま使い、bare キーだけ
   fallback-ns で補う（このリポジトリでは全キーが既に名前空間付きの想定）。"
  [content fallback-ns]
  (into {:db/id -1}
        (map (fn [[k v]]
               [(if (namespace k) k (namespaced-key fallback-ns k))
                (attr-value v)]))
        content))

(defn schema-attrs
  [content ns-name preserve-ns?]
  (for [[k v] content]
    (let [{:keys [type card]} (classify v)
          ident (if (and preserve-ns? (namespace k)) k (namespaced-key ns-name k))]
      {:db/ident ident
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
                              ";; 手編集禁止 — 再生成すると上書きされる。\n\n"
                              (pr-str merged)
                              "\n"))
    merged))

(defn wrap-map! [rel-path ns-name & [preserve-ns?]]
  (let [f (io/file root rel-path)
        content (slurp-edn f)]
    (if (already-tx-data? content)
      (println "skip (already tx-data):" rel-path)
      (let [entity (if preserve-ns?
                     (entity-from-map-preserve-ns content ns-name)
                     (entity-from-map content ns-name))
            attrs (schema-attrs content ns-name preserve-ns?)]
        (spit f (pr-str [entity]))
        (merge-schema! attrs)
        (println "wrapped" rel-path "->" (count entity) "attrs, ns=" ns-name "preserve-ns=" (boolean preserve-ns?))))))

(defn -main [& args]
  (let [[mode a b c] args]
    (case mode
      "wrap-map" (wrap-map! a b false)
      "wrap-map-preserve-ns" (wrap-map! a b true)
      (do (println "usage: bb edn-datomize.bb [wrap-map <path> <ns> | wrap-map-preserve-ns <path> <fallback-ns>]")
          (System/exit 1)))))

(apply -main *command-line-args*)
