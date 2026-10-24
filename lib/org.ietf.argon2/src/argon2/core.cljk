(ns argon2.core
  "[RFC 9106](https://www.rfc-editor.org/rfc/rfc9106) Argon2 — Argon2d,
  Argon2i and Argon2id — in portable `.cljc`.

  ## Why this exists

  `kotoba-lang/pqh` names the suite `argon2id-v1`, defines an `IKdf`
  capability for it, and says in its own docstring that no Argon2id math
  lives there: a host must inject BouncyCastle on the JVM or
  `@noble/hashes` under ClojureScript. That is a reasonable seam and a real
  gap — there was no in-language implementation to serve as the reference a
  provider is checked against, and no implementation at all on a host that
  has neither.

  ## Read this before using it for passwords

  Argon2 is memory-hard on purpose, and this implementation is written for
  correctness and portability rather than speed. **Measure it at your
  parameters on your runtime before putting it on a login path.** The
  numbers this library was landed with are in the README; they are not
  repeated here, because a number in a docstring outlives the machine it was
  taken on.

  Where a vetted native provider exists, prefer it and use this as the
  oracle it is checked against. That is the honest division of labour, and
  it is the one `pqh`'s capability seam already assumes.

  ## Output

  A vector of ints in 0..255 — a value, so it compares and prints. Convert
  at your own edge.

  ## Errors

  Returned, never thrown, by `argon2`; `argon2!` throws instead. `:reason`
  is a keyword naming the rule from §3.1 that rejected the parameters, and
  those keywords are contract."
  (:require [argon2.compress :as c]
            [argon2.u32 :as u]
            [blake2.core :as b]))

(def version
  "0x13. Version 0x10 exists and is not implemented: it differs in the
  second-pass rule (it overwrites where 0x13 XORs), and supporting a variant
  nothing here produces would be a second code path nothing here tests."
  0x13)

(def types {:argon2d 0 :argon2i 1 :argon2id 2})

(def sync-points
  "Four slices per lane. Fixed by the specification, not a parameter: the
  lane synchronisation that makes parallel Argon2 deterministic is defined
  in terms of it."
  4)

(def addresses-per-block 128)

;; ── hashing helpers ──────────────────────────────────────────────────────────

(defn- bytes->ints
  "BLAKE2b hands back a `byte-array` on the JVM, whose elements are SIGNED.
  Everything downstream indexes, shifts and compares these, so they are
  normalised here once rather than at each of the dozen places that would
  otherwise have to remember."
  [bs]
  (mapv #(bit-and (int %) 0xFF) (seq bs)))

(defn- h64 [data] (bytes->ints (b/blake2b data {:digest-size 64})))
(defn- h-tau [tau data] (bytes->ints (b/blake2b data {:digest-size tau})))

(defn- h-prime
  "H', RFC 9106 §3.3 — BLAKE2b stretched to an arbitrary output length.

  Up to 64 bytes it is BLAKE2b with the length prefixed. Beyond that it
  chains 64-byte digests and takes the first 32 bytes of each, which is why
  the output of consecutive calls does not simply extend: the halving is
  what stops an attacker who has the first 32 bytes from continuing the
  chain."
  [tau data]
  (let [pre (into (u/le32 tau) data)]
    (if (<= tau 64)
      (h-tau tau pre)
      (let [r (- (quot (+ tau 31) 32) 2)]
        (loop [i 1 v (h64 pre) acc []]
          (let [acc (into acc (subvec v 0 32))]
            (if (= i r)
              (into acc (h-tau (- tau (* 32 r)) v))
              (recur (inc i) (h64 v) acc))))))))

(defn- h0
  "The 64-byte seed every block descends from, RFC 9106 §3.2 step 1.

  Every parameter is length-prefixed and folded in, which is what makes two
  hashes with the same password and salt but different memory or parallelism
  unrelated rather than merely truncated versions of each other."
  [{:keys [p tau m t y password salt secret ad]}]
  (h64 (reduce into []
               [(u/le32 p) (u/le32 tau) (u/le32 m) (u/le32 t)
                (u/le32 version) (u/le32 y)
                (u/le32 (count password)) password
                (u/le32 (count salt)) salt
                (u/le32 (count secret)) secret
                (u/le32 (count ad)) ad])))

;; ── addressing ───────────────────────────────────────────────────────────────

(defn- reference-area-size
  "How many earlier blocks the one being computed may point at, §3.4.1.2.

  The four cases are not interchangeable and the asymmetry is the point: on
  the first pass a block can only look backwards, and only into lanes whose
  slice is already finished, because anything else would make the result
  depend on thread scheduling."
  [pass slice k same-lane? segment-length lane-length]
  (cond
    (and (zero? pass) (zero? slice)) (dec k)
    (zero? pass) (if same-lane?
                   (+ (* slice segment-length) k -1)
                   (+ (* slice segment-length) (if (zero? k) -1 0)))
    :else (if same-lane?
            (+ (- lane-length segment-length) k -1)
            (+ (- lane-length segment-length) (if (zero? k) -1 0)))))

(defn- absolute-position
  "Map J1 onto a reference block, §3.4.1.2.

  The squaring is deliberate: it biases the choice towards recent blocks,
  which is what forces an attacker trading memory for computation to redo
  the most expensive part. `(x*x) >> 32` needs the full 64-bit product, so
  it goes through `mul32` rather than a 32-bit operator that would silently
  keep the wrong half."
  [j1 ref-area pass slice segment-length lane-length]
  (let [x (nth (u/mul32 j1 j1) 0)
        y (nth (u/mul32 ref-area x) 0)
        rel (- ref-area 1 y)
        start (if (zero? pass)
                0
                (if (= slice (dec sync-points)) 0 (* (inc slice) segment-length)))]
    (mod (+ start rel) lane-length)))

;; ── the fill loop ────────────────────────────────────────────────────────────

(defn- data-independent?
  "Argon2i always; Argon2id only on the first pass's first two slices. That
  hybrid is the whole point of the id variant: data-independent while the
  memory an attacker could probe is still small, data-dependent afterwards."
  [y pass slice]
  (or (= y 1) (and (= y 2) (zero? pass) (< slice 2))))

(defn- address-block!
  "Regenerate the address block for a data-independent segment, §3.4.1.1.

  `G(zero, G(zero, Z))` where Z carries the position and the counter. The
  double application is not redundant: a single G of a mostly-zero input
  leaves structure that shows up in the addresses."
  [mem zero-off input-off addr-off counter r z tmp]
  ;; input word 6 is the counter, incremented before each generation
  (let [lane (+ input-off 12)]
    (u/wr mem lane (u/u32 counter))
    (u/wr mem (inc lane) (u/u32 (quot counter 4294967296))))
  (c/fill-block! mem zero-off input-off addr-off false r z tmp)
  (c/fill-block! mem zero-off addr-off addr-off false r z tmp))

(defn- fill!
  [mem {:keys [p t y lane-length segment-length]} scratch]
  (let [{:keys [r z tmp zero-off input-off addr-off]} scratch
        blk (fn [lane col] (* c/block-lanes (+ (* lane lane-length) col)))]
    (dotimes [pass t]
      (dotimes [slice sync-points]
        (dotimes [lane p]
          (let [indep? (data-independent? y pass slice)
                first-seg? (and (zero? pass) (zero? slice))
                start (if first-seg? 2 0)
                counter (atom 0)]
            (when indep?
              ;; Z = LE64(pass) LE64(lane) LE64(slice) LE64(m') LE64(t) LE64(y)
              (dotimes [i c/block-lanes] (u/wr mem (+ input-off i) 0))
              (doseq [[w v] [[0 pass] [1 lane] [2 slice]
                             [3 (* p lane-length)] [4 t] [5 y]]]
                (u/wr mem (+ input-off (* 2 w)) (u/u32 v))
                (u/wr mem (+ input-off (* 2 w) 1) (u/u32 (quot v 4294967296))))
              (when first-seg?
                (swap! counter inc)
                (address-block! mem zero-off input-off addr-off @counter r z tmp)))
            (loop [k start]
              (when (< k segment-length)
                (when (and indep? (zero? (mod k addresses-per-block)))
                  (swap! counter inc)
                  (address-block! mem zero-off input-off addr-off @counter r z tmp))
                (let [col (+ (* slice segment-length) k)
                      prev-col (if (zero? col) (dec lane-length) (dec col))
                      prev (blk lane prev-col)
                      [j2 j1] (if indep?
                                (let [w (mod k addresses-per-block)
                                      off (+ addr-off (* 2 w))]
                                  [(u/rd mem (inc off)) (u/rd mem off)])
                                (c/word0 mem prev))
                      ref-lane (if (and (zero? pass) (zero? slice)) lane (mod j2 p))
                      same? (= ref-lane lane)
                      area (reference-area-size pass slice k same? segment-length lane-length)
                      ref-col (absolute-position j1 area pass slice segment-length lane-length)]
                  (c/fill-block! mem prev (blk ref-lane ref-col) (blk lane col)
                                 (pos? pass) r z tmp))
                (recur (inc k))))))))))

;; ── parameter validation ─────────────────────────────────────────────────────

(defn- validate [{:keys [p tau m t salt]}]
  (cond
    (not (<= 1 p 16777215)) {:reason :parallelism-out-of-range :value p}
    (< tau 4) {:reason :tag-too-short :value tau}
    (< (count salt) 8) {:reason :salt-too-short :value (count salt)}
    (< m (* 8 p)) {:reason :memory-too-small :value m :minimum (* 8 p)}
    (< t 1) {:reason :iterations-too-few :value t}
    :else nil))

;; ── public ───────────────────────────────────────────────────────────────────

(defn- ->ints [x] (if (nil? x) [] (mapv #(bit-and (int %) 0xFF) (seq x))))

(defn utf8
  "A string as a vector of UTF-8 bytes.

  Present because a password is almost always a string, and the obvious
  translation is wrong on one runtime in a way that produces a plausible
  answer rather than an error: `(mapv int \"Password\")` gives the code
  points on the JVM and a vector of ZEROS under ClojureScript, where a
  character is a one-character string and `int` of one is not a code point.
  Two different passwords then hash identically. This library's own test
  suite hit exactly that, and only the ClojureScript runner saw it."
  [s]
  #?(:clj (mapv #(bit-and % 0xFF) (.getBytes ^String s "UTF-8"))
     :cljs (vec (array-seq (.encode (js/TextEncoder.) s)))))

(defn argon2
  "Derive `:tag-length` bytes from `:password` and `:salt`.

    :type          :argon2d | :argon2i | :argon2id  (default :argon2id)
    :password      bytes. Required.
    :salt          bytes, at least 8. Required.
    :secret        bytes, optional — RFC 9106's K, a key the verifier holds
                   and the stored hash does not reveal.
    :associated-data  bytes, optional — RFC 9106's X.
    :parallelism   lanes, default 1
    :memory-kib    default 19456 (OWASP's minimum recommendation)
    :iterations    default 2
    :tag-length    default 32

  Returns `{:status :ok :tag [bytes]}` or `{:status :error :reason kw}`."
  [{:keys [type password salt secret associated-data
           parallelism memory-kib iterations tag-length]
    :or {type :argon2id parallelism 1 memory-kib 19456 iterations 2 tag-length 32}}]
  (let [y (get types type)
        args {:p parallelism :tau tag-length :m memory-kib :t iterations :y y
              :password (->ints password) :salt (->ints salt)
              :secret (->ints secret) :ad (->ints associated-data)}]
    (if (nil? y)
      {:status :error :reason :unknown-type :type type}
      (if-let [bad (validate args)]
        (merge {:status :error} bad)
        (let [p parallelism
              ;; m' is rounded DOWN to a multiple of 4p, §3.1. A caller who
              ;; asks for 19456 with p=3 does not get 19456; the tag depends
              ;; on m as asked (through H0) and on m' as used, and those are
              ;; different numbers on purpose.
              m' (* 4 p (quot memory-kib (* 4 p)))
              lane-length (quot m' p)
              segment-length (quot lane-length sync-points)
              ;; three scratch blocks past the end: zero, address input,
              ;; address output. Allocating them inside the arena keeps the
              ;; whole computation to one array.
              mem (u/alloc (* c/block-lanes (+ m' 3)))
              zero-off (* c/block-lanes m')
              input-off (* c/block-lanes (+ m' 1))
              addr-off (* c/block-lanes (+ m' 2))
              seed (h0 args)]
          (dotimes [i p]
            (c/bytes->block! mem (* c/block-lanes i lane-length)
                             (h-prime 1024 (reduce into seed [(u/le32 0) (u/le32 i)])))
            (c/bytes->block! mem (* c/block-lanes (+ (* i lane-length) 1))
                             (h-prime 1024 (reduce into seed [(u/le32 1) (u/le32 i)]))))
          (fill! mem {:p p :t iterations :y y
                      :lane-length lane-length :segment-length segment-length}
                 {:r (u/alloc c/block-lanes) :z (u/alloc c/block-lanes)
                  :tmp (u/alloc 2)
                  :zero-off zero-off :input-off input-off :addr-off addr-off})
          ;; C = the XOR of every lane's last block
          (let [final (* c/block-lanes (dec lane-length))]
            (dotimes [i (dec p)]
              (let [src (* c/block-lanes (+ (* (inc i) lane-length) (dec lane-length)))]
                (dotimes [j c/block-lanes]
                  (u/wr mem (+ final j)
                        (u/u32 (bit-xor (u/rd mem (+ final j)) (u/rd mem (+ src j))))))))
            {:status :ok :tag (h-prime tag-length (c/block->bytes mem final))}))))))

(defn argon2!
  "`argon2`, throwing on rejected parameters."
  [opts]
  (let [r (argon2 opts)]
    (if (= :ok (:status r))
      (:tag r)
      (throw (ex-info (str "argon2: " (name (:reason r))) r)))))

(defn hex
  "Lowercase hex. The mask is not decoration: a signed byte that reached here
  would render as `-7c`, which is two characters longer than a byte and
  silently wrong rather than obviously so."
  [bs]
  (apply str (map (fn [b]
                    (let [b (bit-and (int b) 0xFF)
                          s #?(:clj (Integer/toString b 16)
                               :cljs (.toString b 16))]
                      (if (= 1 (count s)) (str "0" s) s)))
                  bs)))

(defn unhex [s]
  (mapv (fn [pair] #?(:clj (Integer/parseInt (apply str pair) 16)
                      :cljs (js/parseInt (apply str pair) 16)))
        (partition 2 s)))
