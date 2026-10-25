(ns kotobase.engine.prolly.cursor
  "Direct asynchronous, range-pruned reads over Arrangement snapshots."
  (:require [kotoba.lang.text :as str]
            [arrangement.core :as arrangement]
            [ipld.core :as ipld]
            [ipld.value :as value]
            [kotobase.engine.canonical :as canonical]
            [kotobase.engine.prolly :as prolly]
            [prolly-tree.core :as tree]))

(def ^:private batch-size 24)

(def ^:private index-order
  {"spo" [:s :p :o] "pso" [:p :s :o]
   "pos" [:p :o :s] "ocp" [:o :p :s]})

(defn- plan [[s p o]]
  (cond
    (and s p o) ["spo" [s p o]]
    (and s p) ["spo" [s p]]
    (and p o) ["pos" [p o]]
    s ["spo" [s]]
    p ["pso" [p]]
    :else ["spo" []]))

(defn- pmap-async [f values]
  (reduce
   (fn [acc batch]
     (.then acc
            (fn [results]
              (-> (js/Promise.all (into-array (map f batch)))
                  (.then #(into results %))))))
   (js/Promise.resolve [])
   (partition-all batch-size values)))

(defn- prefix-async [blind-fn values]
  (if (empty? values)
    (js/Promise.resolve "")
    (-> (pmap-async #(blind-fn (arrangement/blind-input %)) values)
        (.then (fn [tokens]
                 (str "[" (str/join " " (map pr-str tokens))
                      (when (< (count values) 3) " ")))))))

(defn- checked-node [async-get-fn cid]
  (-> (async-get-fn cid)
      (.then (fn [bytes]
               (when-not bytes
                 (throw (ex-info "snapshot block is missing"
                                 {:type :kotobase.engine/block-not-found
                                  :cid cid})))
               (let [actual (ipld/cid bytes)]
                 (when-not (= cid actual)
                   (throw (ex-info "snapshot block CID mismatch"
                                   {:type :ipld/cid-mismatch
                                    :expected-cid cid :actual-cid actual}))))
               (ipld/decode bytes)))))

(defn- live-coordinates [history basis-t]
  (reduce (fn [coordinates datom]
            (if (> (:t datom) basis-t)
              coordinates
              (let [k (canonical/logical-datom-key datom)]
                (if (:added datom)
                  (assoc coordinates k (:t datom))
                  (dissoc coordinates k)))))
          {} history))

(defn- decode-row [index triple]
  (let [{:keys [s p o]} (zipmap (index-order index) triple)
        row {:e (prolly/decode-component s)
             :a (prolly/decode-component p)
             :v (prolly/decode-component o)
             :added true}]
    row))

(defn- coordinate-key [blind-fn row]
  (-> (blind-fn
       (canonical/canonical-string
        ["kotobase.datom-coordinate/v1" (canonical/logical-datom-key row)]))
      (.then #(str "t/" %))))

(defn- indexed-coordinate
  [async-get-fn blind-fn decrypt-fn metadata-root row]
  (-> (coordinate-key blind-fn row)
      (.then
       (fn [key]
         (-> (tree/scan-prefix-async async-get-fn metadata-root key)
             (.then
              (fn [entries]
                (some (fn [[entry-key ciphertext]]
                        (when (= key entry-key) ciphertext))
                      entries))))))
      (.then (fn [ciphertext]
               (when-not ciphertext
                 (throw (ex-info "transaction coordinate is missing"
                                 {:type :kotobase.engine/missing-coordinate
                                  :datom (canonical/logical-datom-key row)})))
               (decrypt-fn ciphertext)))
      (.then value/decode-value)
      (.then #(assoc row :t %))))

(defn- matches? [[pe pa pv] {:keys [e a v]}]
  (and (or (nil? pe) (= pe e))
       (or (nil? pa) (= pa a))
       (or (nil? pv) (= pv v))))

(defn scan
  [async-get-fn blind-fn decrypt-fn snapshot-cid history metadata-root basis-t pattern
   {:keys [limit]}]
  (if (nil? snapshot-cid)
    (js/Promise.resolve [])
    (let [encoded (mapv #(when (some? %) (prolly/encode-component %)) pattern)
          [index components] (plan encoded)
          coordinates (when history (live-coordinates history basis-t))]
      (-> (checked-node async-get-fn snapshot-cid)
          (.then
           (fn [snapshot]
             (let [schema-version (get snapshot "schema-version")
                   _ (when-not (= arrangement/current-schema-version schema-version)
                       (throw (ex-info "async cursor requires current snapshot schema"
                                       {:type :kotobase.engine/unsupported-snapshot
                                        :schema-version schema-version})))
                   root (some-> (get-in snapshot ["index-roots" index])
                                ipld/link-cid)]
               (-> (prefix-async blind-fn components)
                   (.then #(tree/scan-prefix-async async-get-fn root %))))))
          (.then
           (fn [entries]
             (pmap-async
              (fn [[_ ciphertext]]
                (-> (decrypt-fn ciphertext)
                    (.then value/decode-value)))
              entries)))
         (.then
           (fn [triples]
             (let [ordered (->> triples
                                (map #(decode-row index %))
                                (filter #(matches? pattern %))
                                canonical/canonical-datoms)
                   rows (vec (if limit (take limit ordered) ordered))]
               (if metadata-root
                 (pmap-async #(indexed-coordinate async-get-fn blind-fn
                                                   decrypt-fn metadata-root %)
                             rows)
                 (js/Promise.resolve
                  (mapv #(assoc % :t (get coordinates
                                          (canonical/logical-datom-key %)))
                        rows))))))))))
