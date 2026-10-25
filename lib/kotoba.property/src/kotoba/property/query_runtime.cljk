(ns kotoba.property.query-runtime
  "In-memory Datalog query layer over property EDN records.

  Replaces DataScript (JVM `datascript.core` and npm `datascript`) with
  `kotoba-lang/datalog`. Attribute names and keyword values are stored as
  bare strings so the existing nbb script query strings keep working unchanged."
  (:require [kotoba.lang.edn :as edn]
            [datalog.core :as dl]
            [datalog.index :as index]))

(defn- attr-name [k]
  (if (keyword? k)
    (if-let [ns* (namespace k)]
      (str ns* "/" (name k))
      (name k))
    (str k)))

(defn- attr-value [v]
  (cond
    (keyword? v) (name v)
    (map? v) (pr-str v)
    (or (vector? v) (seq? v) (set? v)) (pr-str v)
    (nil? v) ""
    :else v))

(defn- parse-vector-query [query]
  (let [qvec (if (string? query) (edn/read-string query) query)
        idx-in (or (first (keep-indexed #(when (= %2 :in) %1) qvec)) -1)
        idx-where (or (first (keep-indexed #(when (= %2 :where) %1) qvec)) -1)
        find-syms (vec (subvec qvec 1 idx-in))
        in-syms (when (pos? idx-in) (vec (subvec qvec (inc idx-in) idx-where)))
        where-clauses (when (pos? idx-where) (vec (subvec qvec (inc idx-where))))]
    {:find find-syms :in in-syms :where where-clauses}))

(defn- norm-ground [x]
  (cond
    (symbol? x) x
    (keyword? x) (attr-name x)
    :else x))

(defn- norm-clause [clause]
  (mapv norm-ground clause))

(defn db
  "Build a datalog db from a seq of entity maps (one map per entity)."
  [records]
  (loop [records (seq records), db (index/empty-db), n 0]
    (if-not records
      db
      (let [record (first records)
            subject (str "e" n)
            db' (reduce (fn [acc [k v]]
                          (if (= k :db/id)
                            acc
                            (index/assert-quad acc
                                               {:s subject
                                                :p (attr-name k)
                                                :o (attr-value v)}
                                               (constantly false))))
                        db
                        record)]
        (recur (next records) db' (inc n))))))

(defn q
  "Run a DataScript-shaped vector query (string or read form) over `db`.
  Optional `inputs` follow `:in` after the `$` db placeholder."
  [db query & inputs]
  (let [{:keys [find in where]} (parse-vector-query query)
        in-syms (vec (remove #{'$} (or in [])))
        _ (when (not= (count in-syms) (count inputs))
            (throw (ex-info "query-runtime: :in arity mismatch"
                            {:in in-syms :inputs inputs})))]
    (dl/q db {:find find :in in :where (mapv norm-clause where)}
          (constantly true)
          inputs)))
