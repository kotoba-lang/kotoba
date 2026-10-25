#!/usr/bin/env kbb
;; edn-datomize.bb — wrap a resource .edn file's top-level map into a
;; Datomic/Datascript tx-data vector: [{:db/id -1 <ns>/<key> <value> ...}].
;;
;; - Namespace is derived from the file's path (dot-joined dir + stem,
;;   underscores -> dashes) UNLESS a key is already namespaced
;;   (idiomatic `:foo/bar`), in which case the existing namespace is kept
;;   and only genuinely bare keys get the file-derived namespace.
;; - Scalars (string/long/double/boolean/keyword) and homogeneous
;;   collections of scalars stay as live Datomic-valid values.
;; - Non-scalar values (nested maps, vectors-of-maps) are pr-str'd into a
;;   blob string (still round-trippable via clojure.edn/read-string).
;; - Accumulates repo-root schema.edn: a list of
;;   {:db/ident :db/valueType :db/cardinality} maps (Datomic+Datascript
;;   compatible — no Datomic-only keys like :db.install/_attribute).
;;
;; Usage: bb scripts/edn-datomize.bb <repo-relative-path-to-edn> [...]
;; Writes the transformed file in place and merges into ./schema.edn.

(require '[clojure.edn :as edn]
         '[clojure.string :as str]
         '[clojure.java.io :as io])

(def repo-root (System/getProperty "user.dir"))
(def schema-path (str repo-root "/schema.edn"))

(defn- scalar? [v]
  (or (string? v) (integer? v) (double? v) (boolean? v) (keyword? v)))

(defn- classify [v]
  (cond
    (scalar? v) :scalar
    (and (vector? v) (every? scalar? v)) :scalar-coll
    :else :blob))

(defn- value-type [v]
  (cond
    (keyword? v) :db.type/keyword
    (string? v)  :db.type/string
    (boolean? v) :db.type/boolean
    (integer? v) :db.type/long
    (double? v)  :db.type/double
    :else        :db.type/string))

(defn- attr-value [v]
  (case (classify v)
    :scalar v
    :scalar-coll v
    :blob (pr-str v)))

(defn- schema-entry [attr v]
  (case (classify v)
    :scalar {:db/ident attr :db/valueType (value-type v) :db/cardinality :db.cardinality/one}
    :scalar-coll {:db/ident attr
                  :db/valueType (value-type (first v))
                  :db/cardinality :db.cardinality/many}
    :blob {:db/ident attr :db/valueType :db.type/string :db/cardinality :db.cardinality/one}))

(defn- ns-from-path [rel-path]
  (let [no-ext (str/replace rel-path #"\.edn$" "")
        segs   (str/split no-ext #"/")]
    (str/join "." (map #(str/replace % #"_" "-") segs))))

(defn- already-namespaced? [k]
  (boolean (namespace k)))

(defn- promote-key [file-ns k]
  (if (already-namespaced? k)
    k
    (keyword file-ns (name k))))

(defn- entity-from-map [file-ns m]
  (into {:db/id -1}
        (map (fn [[k v]]
               (let [attr (promote-key file-ns k)]
                 [attr (attr-value v)])))
        m))

(defn- schema-entries-from-map [file-ns m]
  (map (fn [[k v]] (schema-entry (promote-key file-ns k) v)) m))

(defn- read-schema! []
  (if (.exists (io/file schema-path))
    (vec (edn/read-string (slurp schema-path)))
    []))

(defn- merge-schema! [new-entries]
  (let [existing (read-schema!)
        by-ident (into {} (map (juxt :db/ident identity)) existing)
        merged   (vals (reduce (fn [m e] (assoc m (:db/ident e) e)) by-ident new-entries))
        sorted   (sort-by (comp str :db/ident) merged)]
    (spit schema-path
          (with-out-str
            (println ";; schema.edn — accumulated Datomic/Datascript attribute schema")
            (println ";; for this repo's tx-data-shaped .edn resources. Generated/")
            (println ";; maintained by scripts/edn-datomize.bb — do not hand-edit stale")
            (println ";; entries away, re-run the script instead.")
            (print "[")
            (doseq [[i e] (map-indexed vector sorted)]
              (when (pos? i) (print " "))
              (print (pr-str e))
              (println))
            (println "]")))))

(defn- fmt-tx-data [entity]
  (str "[{:db/id -1\n"
       (str/join "\n"
                  (map (fn [[k v]] (str "  " (pr-str k) " " (pr-str v)))
                       (dissoc entity :db/id)))
       "}]\n"))

(defn wrap-map! [rel-path]
  (let [abs-path (str repo-root "/" rel-path)
        content  (edn/read-string (slurp abs-path))]
    (when-not (map? content)
      (throw (ex-info "edn-datomize: top-level content is not a map" {:path rel-path})))
    (let [file-ns  (ns-from-path rel-path)
          entity   (entity-from-map file-ns content)
          entries  (schema-entries-from-map file-ns content)]
      (spit abs-path (fmt-tx-data entity))
      (merge-schema! entries)
      (println "wrapped:" rel-path "(ns" file-ns ")"))))

(defn -main [& paths]
  (doseq [p paths] (wrap-map! p)))

(apply -main *command-line-args*)
