(ns kotoba.lang.witness-quorum.selector
  "nbb/ClojureScript port of selector.clj -- see that file for full docs
  (deterministic witness selection: same record-cid -> same cells,
  every time). Uses Node's synchronous crypto.createHash (not the async
  Web Crypto subtle.digest) to keep the same synchronous API shape as
  the JVM version."
  (:require ["crypto" :as crypto]))

(defn fleet-cell
  "Build a fleet cell map from a node hostname/name + cell-id."
  [node cell-id]
  {:node node :cell-id cell-id :key (str node "::" cell-id)})

(defn- sha256-hex [s]
  (-> (.createHash crypto "sha256") (.update s "utf8") (.digest "hex")))

(defn quorum-group
  "Quorum group identifier for a record -- sha256(record-cid)[:16] hex."
  [record-cid]
  (subs (sha256-hex record-cid) 0 16))

(defn select-witnesses
  "Select `quorum-size` (default 5) witnesses for a record from `fleet`.
  Same algorithm as selector.clj: sort by :key, offset by
  sha256(record-cid) mod fleet-len, take quorum-size distinct cells."
  ([record-cid fleet] (select-witnesses record-cid fleet 5))
  ([record-cid fleet quorum-size]
   (let [n (count fleet)]
     (when (< n quorum-size)
       (throw (js/Error. (str "witness-quorum: fleet has " n " cells, cannot select quorum of " quorum-size))))
     (when (< quorum-size 1)
       (throw (js/Error. (str "witness-quorum: quorum-size must be >=1, got " quorum-size))))
     (let [sorted (vec (sort-by :key fleet))
           digest-int (js/BigInt (str "0x" (sha256-hex record-cid)))
           offset (js/Number (mod digest-int (js/BigInt n)))]
       (loop [i 0 selected [] seen #{}]
         (cond
           (>= (count selected) quorum-size) selected

           (>= i (* n 2))
           (throw (js/Error. "witness-quorum: witness selection loop did not converge -- fleet may have duplicate keys"))

           :else
           (let [idx (mod (+ offset i) n)
                 cell (nth sorted idx)]
             (if (contains? seen (:key cell))
               (recur (inc i) selected seen)
               (recur (inc i) (conj selected cell) (conj seen (:key cell)))))))))))

(defn flatten-fleet
  "Flatten the fleet.toml shape (a seq of {:name/:hostname \"...\" :cells [...]})
  into a vector of fleet-cell maps."
  [nodes]
  (vec (mapcat (fn [{:keys [name hostname cells]}]
                 (let [node-key (or hostname name)]
                   (when-not node-key
                     (throw (js/Error. "witness-quorum: fleet node missing both 'name' and 'hostname'")))
                   (map #(fleet-cell node-key %) cells)))
               nodes)))
