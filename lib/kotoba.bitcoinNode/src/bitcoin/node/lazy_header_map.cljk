(ns bitcoin.node.lazy-header-map
  "An immutable map facade over a durable normalized header index.

  Point lookups use a shared bounded LRU. `assoc` and `dissoc` create immutable
  overlays, allowing the pure consensus transition code to run unchanged.
  Iteration is intentionally explicit and materializes the durable index."
  (:import [clojure.lang APersistentMap IHashEq IKVReduce IPersistentMap
            MapEntry MapEquivalence SeqIterator]
           [java.util LinkedHashMap Map$Entry]))

(def ^:private missing (Object.))

(defprotocol OverlayView
  (overlay-entries [value]
    "Return only immutable entries added above the durable backing index.")
  (rebase [value next-overlay]
    "Move current overlay values into the LRU after their durable commit."))

(defn- trim-cache! [^LinkedHashMap cache cache-limit]
  (while (> (.size cache) cache-limit)
    (let [iterator (.iterator (.keySet cache))]
      (.next iterator)
      (.remove iterator))))

(defn- cache-get
  [load-one ^LinkedHashMap cache cache-limit key]
  (locking cache
    (if (.containsKey cache key)
      (.get cache key)
      (let [loaded (or (load-one key) missing)]
        (.put cache key loaded)
        (trim-cache! cache cache-limit)
        loaded))))

(defn- lookup-value
  [load-one cache cache-limit overlay removed key not-found]
  (cond
    (contains? removed key) not-found
    (contains? overlay key) (get overlay key)
    :else
    (let [loaded (cache-get load-one cache cache-limit key)]
      (if (identical? missing loaded) not-found loaded))))

(defn- materialize
  [load-all overlay removed]
  (merge (apply dissoc (load-all) removed) overlay))

(deftype LazyHeaderMap
  [load-one load-all cache-limit ^LinkedHashMap cache overlay removed]
  OverlayView
  (overlay-entries [_] overlay)
  (rebase [_ next-overlay]
    (when-not (map? next-overlay)
      (throw
       (ex-info
        "Lazy header overlay is invalid."
        {:type :bitcoin.node/lazy-header-map-configuration})))
    (locking cache
      (doseq [[key value] overlay]
        (.put cache key value))
      (trim-cache! cache cache-limit))
    (LazyHeaderMap.
     load-one load-all cache-limit cache next-overlay #{}))

  clojure.lang.ILookup
  (valAt [_ key]
    (lookup-value load-one cache cache-limit overlay removed key nil))
  (valAt [_ key not-found]
    (lookup-value
     load-one cache cache-limit overlay removed key not-found))

  clojure.lang.Associative
  (containsKey [_ key]
    (not (identical?
          missing
          (lookup-value
           load-one cache cache-limit overlay removed key missing))))
  (entryAt [_ key]
    (let [value
          (lookup-value
           load-one cache cache-limit overlay removed key missing)]
      (when-not (identical? missing value)
        (MapEntry/create key value))))

  IPersistentMap
  (assoc [_ key value]
    (LazyHeaderMap.
     load-one load-all cache-limit cache
     (assoc overlay key value) (disj removed key)))
  (assocEx [this key value]
    (when (.containsKey this key)
      (throw (RuntimeException. "Key already present")))
    (.assoc this key value))
  (without [_ key]
    (LazyHeaderMap.
     load-one load-all cache-limit cache
     (dissoc overlay key) (conj removed key)))

  clojure.lang.IPersistentCollection
  (count [_]
    (count (materialize load-all overlay removed)))
  (cons [this value]
    (cond
      (instance? Map$Entry value)
      (.assoc this (.getKey ^Map$Entry value) (.getValue ^Map$Entry value))

      (and (vector? value) (= 2 (count value)))
      (.assoc this (nth value 0) (nth value 1))

      :else
      (reduce conj this value)))
  (empty [_] {})
  (equiv [this other]
    (APersistentMap/mapEquals this other))

  clojure.lang.Seqable
  (seq [_]
    (seq (materialize load-all overlay removed)))

  IKVReduce
  (kvreduce [_ f init]
    (reduce-kv f init (materialize load-all overlay removed)))

  java.lang.Iterable
  (iterator [_]
    (SeqIterator. (seq (materialize load-all overlay removed))))

  java.util.Map
  (size [_]
    (count (materialize load-all overlay removed)))
  (isEmpty [_]
    (zero? (count (materialize load-all overlay removed))))
  (containsValue [_ value]
    (.containsValue
     ^java.util.Map (materialize load-all overlay removed) value))
  (get [_ key]
    (lookup-value load-one cache cache-limit overlay removed key nil))
  (put [_ _ _]
    (throw (UnsupportedOperationException. "Immutable map")))
  (remove [_ _]
    (throw (UnsupportedOperationException. "Immutable map")))
  (putAll [_ _]
    (throw (UnsupportedOperationException. "Immutable map")))
  (clear [_]
    (throw (UnsupportedOperationException. "Immutable map")))
  (keySet [_]
    (.keySet ^java.util.Map (materialize load-all overlay removed)))
  (values [_]
    (.values ^java.util.Map (materialize load-all overlay removed)))
  (entrySet [_]
    (.entrySet ^java.util.Map (materialize load-all overlay removed)))

  MapEquivalence

  IHashEq
  (hasheq [this]
    (APersistentMap/mapHasheq this))

  Object
  (equals [this other]
    (APersistentMap/mapEquals this other))
  (hashCode [this]
    (APersistentMap/mapHash this))
  (toString [_]
    (pr-str (materialize load-all overlay removed))))

(defn create
  "Create a map-compatible lazy header index.

  `load-one` returns a value or nil. `load-all` returns the full durable map
  only for explicit iteration/equality operations. Cache size is bounded
  between 1 and 65536 entries."
  ([load-one load-all]
   (create load-one load-all {}))
  ([load-one load-all {:keys [cache-size overlay]
                       :or {cache-size 8192 overlay {}}}]
   (when-not (and (ifn? load-one)
                  (ifn? load-all)
                  (integer? cache-size)
                  (<= 1 cache-size 65536)
                  (map? overlay))
     (throw
      (ex-info
       "Lazy header map configuration is invalid."
       {:type :bitcoin.node/lazy-header-map-configuration})))
   (LazyHeaderMap.
    load-one load-all cache-size
    (LinkedHashMap. 16 0.75 true)
    overlay #{})))

(defn lazy-header-map? [value]
  (instance? LazyHeaderMap value))
