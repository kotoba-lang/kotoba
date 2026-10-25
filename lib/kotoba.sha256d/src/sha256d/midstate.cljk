(ns sha256d.midstate
  "Bitcoin block-header mining's classic optimization: an 80-byte header splits into
  exactly two 64-byte compression blocks once padded (80 + 1 + 39 zero + 8 length =
  128 = 2x64). The first block covers version + prev-block-hash + a 36-byte prefix of
  the merkle root -- all constant while a miner iterates the nonce for a fixed
  template. Caching the compression state after that first block ('the midstate') and
  only re-running the second block's 64 rounds per attempt skips re-doing the first
  block's 64 rounds every single time, roughly halving the compression work of the
  *inner* SHA-256 per nonce trial (the outer wrapping SHA-256 over the 32-byte inner
  digest is unaffected -- it's already minimal, one block).

  This is exactly the kind of implementation-strategy variation sha256d.evolve's
  Reflection gate exists to check: `header-hash` below is verified equivalent to
  plain `sha256d.core/sha256d-bytes` on the full header, not benchmarked on faith."
  (:require [sha256d.core :as core]))

(def header-length-bytes 80)
(def header-length-bits-be
  "80 bytes = 640 bits as an 8-byte big-endian count -- always the same for a Bitcoin
  block header, so it's a constant rather than computed per call."
  [0 0 0 0 0 0 0x02 0x80])

(defn midstate
  "Compression state after an 80-byte header's constant first 64-byte chunk."
  [header-bytes]
  {:pre [(= header-length-bytes (count header-bytes))]}
  (core/compress core/H0 (subvec (vec header-bytes) 0 64)))

(defn header-hash-with
  "Like `header-hash` but with an injectable compression strategy used for BOTH the inner
  chunk2 compression and the outer 32-byte SHA-256 -- so a miner can run the whole per-nonce
  hash through a platform fast path (`sha256d.core/compress-primitive-inline` on the JVM,
  `compress-v8-inline` on cljs) while still reusing the cached midstate. This is where the two
  big wins compose: midstate skips chunk1's 64 rounds per nonce, and the fast compress cuts the
  per-compression cost of the remaining work. `header-hash` is this with the reference `compress`."
  [compress-fn mid tail-16-bytes]
  {:pre [(= 16 (count tail-16-bytes))]}
  (let [chunk2 (-> (vec tail-16-bytes)
                    (conj 0x80)
                    (into (repeat 39 0))
                    (into header-length-bits-be))
        inner  (core/words->bytes (compress-fn mid chunk2 core/ch core/maj))]
    (core/sha256-bytes-with compress-fn inner core/ch core/maj)))

(defn header-hash
  "sha256d of an 80-byte header, given `mid` (from `midstate` on the same header) and
  the 16 bytes that vary between attempts (merkle-root tail 4B + time 4B + bits 4B +
  nonce 4B, i.e. header bytes [64 80)). Never re-touches the first chunk."
  [mid tail-16-bytes]
  (header-hash-with core/compress mid tail-16-bytes))

(defn header-hash-reference
  "No-caching reference form (recomputes everything from the full header) -- used to
  check `header-hash` against, not for actual mining use."
  [header-bytes]
  (core/sha256d-bytes header-bytes))

;; --- mining nonce search (ties midstate + a fast compress together) ----------------

(defn- leading-zero-bits
  "Number of leading zero bits across a byte-value sequence (MSB-first)."
  [byte-seq]
  (reduce (fn [acc b]
            (if (zero? b)
              (+ acc 8)
              (reduced (+ acc (loop [n 0 x b] (if (>= x 128) n (recur (inc n) (* x 2))))))))
          0
          byte-seq))

(defn search-nonce
  "Scan nonces in [start, start+cnt) for the first header whose sha256d, in Bitcoin display
  order (the byte-reversed on-wire hash), has at least `zero-bits` leading zero bits -- a
  simplified proof-of-work target. `mid` is the header midstate (computed once); `tail-prefix-12`
  the 12 constant tail bytes (merkle-root tail 4 + time 4 + bits 4); the 4-byte little-endian
  nonce is appended per attempt. `compress-fn` selects the compression strategy (pass
  `sha256d.core/compress` for portable, or a fast path). Returns [nonce hash-bytes] or nil.

  This is the concrete Bitcoin payoff of the whole repo: midstate reuse + a fast compress, in
  one loop. Correctness is independent of `compress-fn` (every strategy is bit-identical), so a
  fast path finds the exact same winning nonce as the reference -- only faster."
  [compress-fn mid tail-prefix-12 zero-bits start cnt]
  {:pre [(= 12 (count tail-prefix-12))]}
  (let [prefix (vec tail-prefix-12)]
    (loop [n start i 0]
      (if (>= i cnt)
        nil
        (let [tail16 (conj prefix
                           (bit-and n 0xff)
                           (bit-and (unsigned-bit-shift-right n 8) 0xff)
                           (bit-and (unsigned-bit-shift-right n 16) 0xff)
                           (bit-and (unsigned-bit-shift-right n 24) 0xff))
              h (header-hash-with compress-fn mid tail16)]
          (if (>= (leading-zero-bits (reverse h)) zero-bits)
            [n (vec h)]
            (recur (inc n) (inc i))))))))

#?(:clj
   (defn search-nonce-parallel
     "JVM-only: `search-nonce` split across `n-threads` `future`s over contiguous nonce
     sub-ranges, returning the globally-lowest winning nonce (identical to the single-thread
     `search-nonce` result -- deterministic and testable, not first-to-return). Mining is
     embarrassingly parallel across nonces, so this is the across-core axis (orthogonal to a
     per-core fast compress). Whether it scales near-linearly or is capped by GC/allocation
     contention from the per-nonce `long-array` + result-vector churn is the round-13 question."
     [compress-fn mid tail-prefix-12 zero-bits start cnt n-threads]
     (let [chunk (quot cnt n-threads)
           futs  (mapv (fn [t]
                         (let [s (+ start (* t chunk))
                               c (if (= t (dec n-threads)) (- cnt (* t chunk)) chunk)]
                           (future (search-nonce compress-fn mid tail-prefix-12 zero-bits s c))))
                       (range n-threads))
           hits  (keep deref futs)]
       (when (seq hits) (apply min-key first hits)))))
