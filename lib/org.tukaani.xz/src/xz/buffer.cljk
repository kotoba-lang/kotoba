(ns xz.buffer
  "A growable byte buffer that doubles as the LZ77 dictionary window.

   LZMA back-references reach up to the dictionary size (often 8 MiB) into
   already-produced output, and a match copy is byte-at-a-time because it may
   overlap itself. A persistent vector makes that O(n) allocations for no reason,
   so this is a typed array behind reader conditionals — the same trade-off, for
   the same reason, as `deflate.lz77`'s hash chains. Nothing mutable escapes:
   callers get a plain vector out of `->vector`."
  (:refer-clojure :exclude [bytes]))

#?(:clj  (defn- mk [n] (byte-array n))
   :cljs (defn- mk [n] (js/Uint8Array. n)))

#?(:clj  (defn- rd [a i] (bit-and (aget ^bytes a i) 0xff))
   :cljs (defn- rd [a i] (aget a i)))

#?(:clj  (defn- wr [a i v] (aset-byte a i (unchecked-byte v)))
   :cljs (defn- wr [a i v] (aset a i v)))

#?(:clj  (defn- cap [a] (alength ^bytes a))
   :cljs (defn- cap [a] (.-length a)))

(defn buffer
  "A buffer with `initial` bytes of capacity."
  [initial]
  {:arr (volatile! (mk (max 16 initial))) :len (volatile! 0)})

(defn- ensure! [b n]
  (let [a @(:arr b)]
    (when (> n (cap a))
      (let [bigger (mk (max n (* 2 (cap a))))]
        #?(:clj  (System/arraycopy a 0 bigger 0 @(:len b))
           :cljs (.set bigger (.subarray a 0 @(:len b)) 0))
        (vreset! (:arr b) bigger)))))

(defn size [b] @(:len b))

(defn push!
  "Append one byte."
  [b v]
  (let [n @(:len b)]
    (ensure! b (inc n))
    (wr @(:arr b) n v)
    (vreset! (:len b) (inc n))
    v))

(defn at
  "Byte at absolute position `i`."
  [b i]
  (rd @(:arr b) i))

(defn back
  "Byte `dist` positions before the end (dist 1 = last byte written)."
  [b dist]
  (rd @(:arr b) (- @(:len b) dist)))

(defn copy-match!
  "Copy `len` bytes from `dist` back — byte at a time, because a match may
   overlap itself (`dist` 1 with `len` 100 is a run of one byte)."
  [b dist len]
  (when (> dist @(:len b))
    (throw (ex-info "lzma: back-reference before the start of the stream"
                    {:reason :bad-distance :distance dist :available @(:len b)})))
  (dotimes [_ len]
    (push! b (back b dist))))

(defn append!
  "Append a sequence of bytes."
  [b bs]
  (doseq [v bs] (push! b v)))

(defn ->vector
  "The bytes written, as an ordinary vector."
  ([b] (->vector b 0 (size b)))
  ([b from to]
   (let [a @(:arr b)]
     (persistent!
      (loop [i from acc (transient [])]
        (if (>= i to) acc (recur (inc i) (conj! acc (rd a i)))))))))
