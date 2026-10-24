(ns datalog.singleton
  "A one-element set that costs one object.

  Measured 2026-09-11 (ayatori iterations 26-27, LDBC SNB SF1, 20.6M quads):
  99.5% of the counterpart sets in `:eavt` and `:aevt` hold exactly one
  value, and each `#{v}` is a PersistentHashSet over a PersistentHashMap
  over a BitmapIndexedNode -- about 160 bytes to say `v`. Across four
  indexes that is most of the ~530 bytes a quad cost, and the reason a
  full SF1 (10.9 GB used heap) did not fit a 16 GiB host resident
  (ADR-2609121100).

  `of` returns a value that IS a set to every reader -- `set?`, `contains?`,
  `count`, `seq`, `first`, `get`, `conj`, `disj`, `=` in both directions
  against a real set, `hash` equal to the real set's, `clojure.set` -- so
  no reader of the index changes. `conj` of a second element returns an
  ordinary hash set; `disj` of the element returns `#{}`. What it does not
  carry: metadata (`with-meta` throws), and `transient` (a singleton is
  never made transient; `assert-quads!` conj's it into a real set first).

  On ClojureScript `of` is `#{v}`: the footprint problem is the JVM SUT's,
  and a SCI deftype over the core set protocols is a second thing to be
  wrong about in the runtime that does not have the problem (see the
  note on SCI deftype in `run-tests.cljk`)."
  #?(:clj (:import [clojure.lang IPersistentSet IPersistentCollection Seqable Counted
                    IHashEq IFn AFn Murmur3 RT]
                   [java.util Set Iterator Collections])))

#?(:clj
   (deftype Singleton [v]
     IPersistentSet
     (disjoin [this k] (if (= k v) #{} this))
     (contains [_ k] (= k v))
     (get [_ k] (when (= k v) v))
     IPersistentCollection
     (count [_] 1)
     (cons [this o] (if (= o v) this (hash-set v o)))
     (empty [_] #{})
     (equiv [_ o] (and (instance? Set o) (= 1 (.size ^Set o)) (.contains ^Set o v)))
     Seqable
     (seq [_] (list v))
     Counted
     IHashEq
     (hasheq [this] (Murmur3/hashUnordered this))
     IFn
     (invoke [_ k] (when (= k v) v))
     (applyTo [this args] (AFn/applyToHelper this args))
     Set
     (size [_] 1)
     (isEmpty [_] false)
     (iterator [_] (.iterator (Collections/singletonList v)))
     (^objects toArray [_] (object-array [v]))
     (^objects toArray [_ ^objects a] (.toArray (Collections/singletonList v) a))
     (containsAll [_ c] (every? #(= % v) c))
     (add [_ _] (throw (UnsupportedOperationException.)))
     (remove [_ _] (throw (UnsupportedOperationException.)))
     (addAll [_ _] (throw (UnsupportedOperationException.)))
     (removeAll [_ _] (throw (UnsupportedOperationException.)))
     (retainAll [_ _] (throw (UnsupportedOperationException.)))
     (clear [_] (throw (UnsupportedOperationException.)))
     Object
     (equals [this o] (.equiv this o))
     (hashCode [_] (if (nil? v) 0 (.hashCode v)))
     (toString [_] (str "#{" (pr-str v) "}"))))

#?(:clj (defmethod print-method Singleton [^Singleton s ^java.io.Writer w]
          (.write w "#{") (print-method (.-v s) w) (.write w "}")))

(defn of
  "The set `#{v}`, as cheaply as this platform allows."
  [v]
  #?(:clj (Singleton. v) :cljs #{v}))

(defn singleton?
  "True when `x` is the compact one-element representation (always false on
  ClojureScript, where `of` returns a hash set)."
  [x]
  #?(:clj (instance? Singleton x) :cljs false))
