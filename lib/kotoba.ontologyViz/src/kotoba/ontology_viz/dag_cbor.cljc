(ns kotoba.ontology-viz.dag-cbor
  "Pure, zero-dependency `.cljc` canonical DAG-CBOR encoder, FIPS 180-4 SHA-256,
  and CIDv1 (`dag-cbor` 0x71 / `sha2-256` 0x12 / base32lower) derivation.

  Byte-for-byte compatible with Yataverse PR #83's `encodeOntologyGraphDagCbor`
  (`src/dag-cbor.mjs` + `toDagCborSafe` in `src/ontology.mjs` + `cidFor` in
  `src/cid.mjs`) across JVM Clojure, Babashka, nbb, and ClojureScript."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.validate :as v]))

;; ── Pure .cljc UTF-8 encoding ────────────────────────────────────────────────

(defn utf8-bytes
  "Encode string `s` to a vector of unsigned UTF-8 byte ints (0..255)."
  [s]
  #?(:clj (mapv #(bit-and (int %) 0xff) (.getBytes ^String (str s) "UTF-8"))
     :cljs (let [text (str s)
                 n (.-length text)
                 out (transient [])]
             (loop [i 0
                    acc out]
               (if (>= i n)
                 (persistent! acc)
                 (let [cp (.codePointAt text i)
                       step (if (> cp 0xffff) 2 1)]
                   (cond
                     (< cp 0x80)
                     (recur (+ i step) (conj! acc cp))

                     (< cp 0x800)
                     (recur (+ i step)
                            (-> acc
                                (conj! (bit-or 0xc0 (unsigned-bit-shift-right cp 6)))
                                (conj! (bit-or 0x80 (bit-and cp 0x3f)))))

                     (< cp 0x10000)
                     (recur (+ i step)
                            (-> acc
                                (conj! (bit-or 0xe0 (unsigned-bit-shift-right cp 12)))
                                (conj! (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 6) 0x3f)))
                                (conj! (bit-or 0x80 (bit-and cp 0x3f)))))

                     :else
                     (recur (+ i step)
                            (-> acc
                                (conj! (bit-or 0xf0 (unsigned-bit-shift-right cp 18)))
                                (conj! (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 12) 0x3f)))
                                (conj! (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 6) 0x3f)))
                                (conj! (bit-or 0x80 (bit-and cp 0x3f))))))))))))

;; ── Pure .cljc FIPS 180-4 SHA-256 ────────────────────────────────────────────

(def ^:private sha256-k
  [0x428a2f98 0x71374491 0xb5c0fbcf 0xe9b5dba5 0x3956c25b 0x59f111f1 0x923f82a4 0xab1c5ed5
   0xd807aa98 0x12835b01 0x243185be 0x550c7dc3 0x72be5d74 0x80deb1fe 0x9bdc06a7 0xc19bf174
   0xe49b69c1 0xefbe4786 0x0fc19dc6 0x240ca1cc 0x2de92c6f 0x4a7484aa 0x5cb0a9dc 0x76f988da
   0x983e5152 0xa831c66d 0xb00327c8 0xbf597fc7 0xc6e00bf3 0xd5a79147 0x06ca6351 0x14292967
   0x27b70a85 0x2e1b2138 0x4d2c6dfc 0x53380d13 0x650a7354 0x766a0abb 0x81c2c92e 0x92722c85
   0xa2bfe8a1 0xa81a664b 0xc24b8b70 0xc76c51a3 0xd192e819 0xd6990624 0xf40e3585 0x106aa070
   0x19a4c116 0x1e376c08 0x2748774c 0x34b0bcb5 0x391c0cb3 0x4ed8aa4a 0x5b9cca4f 0x682e6ff3
   0x748f82ee 0x78a5636f 0x84c87814 0x8cc70208 0x90befffa 0xa4506ceb 0xbef9a3f7 0xc67178f2])

(defn- u32 [x] (bit-and x 0xffffffff))

(defn- rotr32 [x n]
  (let [xu (u32 x)]
    (u32 (bit-or (unsigned-bit-shift-right xu n)
                 (bit-shift-left xu (- 32 n))))))

(defn- add32
  ([a b] (u32 (+ a b)))
  ([a b c] (u32 (+ a b c)))
  ([a b c d] (u32 (+ a b c d)))
  ([a b c d e] (u32 (+ a b c d e))))

(defn- sha256-pure [bytes]
  (let [bit-len (* 8 (count bytes))
        bit-hi (quot bit-len 0x100000000)
        bit-lo (mod bit-len 0x100000000)
        pad-zeros (mod (- 56 (mod (+ (count bytes) 1) 64)) 64)
        padded (vec (concat bytes
                            [0x80]
                            (repeat pad-zeros 0)
                            [(bit-and (unsigned-bit-shift-right bit-hi 24) 0xff)
                             (bit-and (unsigned-bit-shift-right bit-hi 16) 0xff)
                             (bit-and (unsigned-bit-shift-right bit-hi 8) 0xff)
                             (bit-and bit-hi 0xff)
                             (bit-and (unsigned-bit-shift-right bit-lo 24) 0xff)
                             (bit-and (unsigned-bit-shift-right bit-lo 16) 0xff)
                             (bit-and (unsigned-bit-shift-right bit-lo 8) 0xff)
                             (bit-and bit-lo 0xff)]))
        n-blocks (quot (count padded) 64)
        [h0 h1 h2 h3 h4 h5 h6 h7]
        (loop [blk 0
               h0 0x6a09e667 h1 0xbb67ae85 h2 0x3c6ef372 h3 0xa54ff53a
               h4 0x510e527f h5 0x9b05688c h6 0x1f83d9ab h7 0x5be0cd19]
          (if (= blk n-blocks)
            [h0 h1 h2 h3 h4 h5 h6 h7]
            (let [base (* blk 64)
                  w (loop [i 0
                           arr (transient [])]
                      (if (= i 64)
                        (persistent! arr)
                        (let [wi (if (< i 16)
                                   (let [o (+ base (* i 4))]
                                     (u32 (bit-or (bit-shift-left (nth padded o) 24)
                                                  (bit-shift-left (nth padded (+ o 1)) 16)
                                                  (bit-shift-left (nth padded (+ o 2)) 8)
                                                  (nth padded (+ o 3)))))
                                   (let [w15 (nth arr (- i 15))
                                         w2 (nth arr (- i 2))
                                         s0 (bit-xor (rotr32 w15 7) (rotr32 w15 18) (unsigned-bit-shift-right w15 3))
                                         s1 (bit-xor (rotr32 w2 17) (rotr32 w2 19) (unsigned-bit-shift-right w2 10))]
                                     (add32 (nth arr (- i 16)) s0 (nth arr (- i 7)) s1)))]
                          (recur (inc i) (conj! arr wi)))))
                  [a b c d e f g h]
                  (loop [i 0
                         a h0 b h1 c h2 d h3 e h4 f h5 g h6 h h7]
                    (if (= i 64)
                      [a b c d e f g h]
                      (let [S1 (bit-xor (rotr32 e 6) (rotr32 e 11) (rotr32 e 25))
                            ch (u32 (bit-xor (bit-and e f) (bit-and (u32 (bit-not e)) g)))
                            t1 (add32 h S1 ch (nth sha256-k i) (nth w i))
                            S0 (bit-xor (rotr32 a 2) (rotr32 a 13) (rotr32 a 22))
                            maj (u32 (bit-xor (bit-and a b) (bit-and a c) (bit-and b c)))
                            t2 (add32 S0 maj)]
                        (recur (inc i)
                               (add32 t1 t2) a b c
                               (add32 d t1) e f g))))]
              (recur (inc blk)
                     (add32 h0 a) (add32 h1 b) (add32 h2 c) (add32 h3 d)
                     (add32 h4 e) (add32 h5 f) (add32 h6 g) (add32 h7 h)))))]
    (vec (mapcat (fn [word]
                   [(bit-and (unsigned-bit-shift-right word 24) 0xff)
                    (bit-and (unsigned-bit-shift-right word 16) 0xff)
                    (bit-and (unsigned-bit-shift-right word 8) 0xff)
                    (bit-and word 0xff)])
                 [h0 h1 h2 h3 h4 h5 h6 h7]))))

(defn sha256-bytes
  "Compute the 32-byte SHA-256 digest of unsigned byte vector `bytes`.
  Uses `java.security.MessageDigest` on JVM/Babashka and pure FIPS 180-4
  SHA-256 on CLJS/nbb (zero Node or browser crypto dependency)."
  [bytes]
  #?(:clj (let [md (java.security.MessageDigest/getInstance "SHA-256")
                arr (byte-array (count bytes))]
            (dotimes [i (count bytes)]
              (aset arr i (unchecked-byte (nth bytes i))))
            (mapv #(bit-and (int %) 0xff) (.digest md arr)))
     :cljs (sha256-pure bytes)))

;; ── Canonical DAG-CBOR Encoder (Yataverse `toDagCborSafe` + `encodeDagCbor`) ─

(defn- key-str [k]
  (cond
    (string? k) k
    (keyword? k) (if (namespace k) (str (namespace k) "/" (name k)) (name k))
    :else (v/fail! :dag-cbor-invalid-key "DAG-CBOR map keys must be strings or keywords" {:key k})))

(defn- compare-byte-vecs
  "DAG-CBOR canonical map-key comparator: byte length first, then unsigned bytewise."
  [a b]
  (let [na (count a) nb (count b)]
    (if (not= na nb)
      (compare na nb)
      (loop [i 0]
        (if (= i na)
          0
          (let [d (- (nth a i) (nth b i))]
            (if (zero? d) (recur (inc i)) d)))))))

(defn- push-head! [out major n]
  (let [prefix (bit-shift-left major 5)]
    (cond
      (< n 24)
      (conj! out (bit-or prefix n))

      (< n 0x100)
      (-> out
          (conj! (bit-or prefix 24))
          (conj! n))

      (< n 0x10000)
      (-> out
          (conj! (bit-or prefix 25))
          (conj! (bit-and (unsigned-bit-shift-right n 8) 0xff))
          (conj! (bit-and n 0xff)))

      (< n 0x100000000)
      (-> out
          (conj! (bit-or prefix 26))
          (conj! (bit-and (unsigned-bit-shift-right n 24) 0xff))
          (conj! (bit-and (unsigned-bit-shift-right n 16) 0xff))
          (conj! (bit-and (unsigned-bit-shift-right n 8) 0xff))
          (conj! (bit-and n 0xff)))

      :else
      ;; Safe JS integer range up to 2^53 - 1
      (let [hi (quot n 0x100000000)
            lo (mod n 0x100000000)]
        (-> out
            (conj! (bit-or prefix 27))
            (conj! (bit-and (unsigned-bit-shift-right hi 24) 0xff))
            (conj! (bit-and (unsigned-bit-shift-right hi 16) 0xff))
            (conj! (bit-and (unsigned-bit-shift-right hi 8) 0xff))
            (conj! (bit-and hi 0xff))
            (conj! (bit-and (unsigned-bit-shift-right lo 24) 0xff))
            (conj! (bit-and (unsigned-bit-shift-right lo 16) 0xff))
            (conj! (bit-and (unsigned-bit-shift-right lo 8) 0xff))
            (conj! (bit-and lo 0xff)))))))

(defn- push-bytes! [out bs]
  (reduce conj! out bs))

(defn- safe-integer-val
  "Return exact integer if `x` is an integer or integer-valued float in JS safe
  integer range; otherwise nil (must use Yataverse decimal wrapper)."
  [x]
  (when (esc/finite-number? x)
    (cond
      (integer? x)
      (when (<= -9007199254740991 x 9007199254740991) x)

      :else
      (let [d (double x)
            r (esc/round-int d)]
        (when (and (== d (double r))
                   (<= -9007199254740991 r 9007199254740991))
          r)))))

(defn- canonical-decimal-str
  "Format a finite non-integer number matching ECMAScript `String(value)` in
  Yataverse `toDagCborSafe` across JVM Clojure, Babashka, nbb, and CLJS."
  [x]
  #?(:cljs (js/String (double x))
     :clj (let [d (double x)
                abs-d (Math/abs d)]
            (if (and (>= abs-d 1.0e-6) (< abs-d 1.0e21))
              (.toPlainString (.stripTrailingZeros (java.math.BigDecimal/valueOf d)))
              (let [s (str d)
                    [mant exp] (str/split s #"E")
                    mant-clean (if (str/ends-with? mant ".0")
                                 (subs mant 0 (- (count mant) 2))
                                 mant)
                    exp-int (Long/parseLong exp)
                    exp-str (if (neg? exp-int) (str "e" exp-int) (str "e+" exp-int))]
                (str mant-clean exp-str))))))

(defn- encode-item! [out x depth]
  (when (> depth 64)
    (v/fail! :max-depth-exceeded "DAG-CBOR encoding depth exceeded 64" {:depth depth}))
  (cond
    (nil? x)
    (conj! out 0xf6)

    (true? x)
    (conj! out 0xf5)

    (false? x)
    (conj! out 0xf4)

    (number? x)
    (do
      (when-not (esc/finite-number? x)
        (v/fail! :dag-cbor-non-finite "DAG-CBOR forbids NaN/Infinity" {:value x}))
      (if-let [iv (safe-integer-val x)]
        (if (>= iv 0)
          (push-head! out 0 iv)
          (push-head! out 1 (- -1 iv)))
        ;; Yataverse toDagCborSafe decimal wrapper for non-integer floats
        (encode-item! out {"$awaiType" "decimal" "value" (canonical-decimal-str x)} (inc depth))))

    (string? x)
    (let [bs (utf8-bytes x)]
      (-> out (push-head! 3 (count bs)) (push-bytes! bs)))

    (keyword? x)
    (let [bs (utf8-bytes (key-str x))]
      (-> out (push-head! 3 (count bs)) (push-bytes! bs)))

    (v/ipld-link? x)
    (let [cid-str (v/extract-cid x)
          cid-bs (v/cidv1-bytes cid-str)
          payload (into [0x00] cid-bs)]
      (-> out
          (conj! 0xd8)
          (conj! 0x2a)
          (push-head! 2 (count payload))
          (push-bytes! payload)))

    (sequential? x)
    (let [out1 (push-head! out 4 (count x))]
      (reduce (fn [acc item] (encode-item! acc item (inc depth))) out1 x))

    (map? x)
    (let [entries (map (fn [[k val]]
                         (let [ks (key-str k)]
                           [(utf8-bytes ks) ks val]))
                       x)
          sorted (sort (fn [[ba _ _] [bb _ _]] (compare-byte-vecs ba bb)) entries)]
      (loop [prev nil
             rem-s sorted]
        (when-let [[kb ks _] (first rem-s)]
          (when (and prev (= prev kb))
            (v/fail! :dag-cbor-duplicate-key (str "duplicate DAG-CBOR map key: " ks) {:key ks}))
          (recur kb (next rem-s))))
      (let [out1 (push-head! out 5 (count sorted))]
        (reduce (fn [acc [kb _ val]]
                  (-> acc
                      (push-head! 3 (count kb))
                      (push-bytes! kb)
                      (encode-item! val (inc depth))))
                out1
                sorted)))

    :else
    (v/fail! :dag-cbor-unsupported-value
             (str "value is not DAG-CBOR encodable: " (pr-str x))
             {:value x})))

(defn encode-dag-cbor
  "Encode `value` into a vector of unsigned canonical DAG-CBOR bytes matching
  Yataverse's `encodeDagCbor(toDagCborSafe(value))` byte-for-byte."
  [value]
  (persistent! (encode-item! (transient []) value 0)))

(defn cidv1-dag-cbor
  "Compute canonical lower-case base32 CIDv1 (`0x01 0x71 0x12 0x20 || sha256(bytes)`)
  for canonical DAG-CBOR byte vector `bytes`."
  [cbor-bytes]
  (let [digest (sha256-bytes cbor-bytes)
        cid-bytes (into [0x01 0x71 0x12 0x20] digest)]
    (str "b" (v/base32-encode cid-bytes))))

(defn encode-ontology-graph-dag-cbor
  "Compute canonical DAG-CBOR bytes and CIDv1 (`graphCid`) for a Yataverse
  `yataverse.ontology.graph/v1` map (excluding any self-referential `graphCid`
  key). Returns `{:cid \"bafyrei...\" :bytes [...] :byte-length n}`."
  [yv-graph]
  (when-not (map? yv-graph)
    (v/fail! :invalid-yataverse-graph "expected Yataverse graph map for DAG-CBOR encoding" {}))
  (let [body (dissoc yv-graph :graphCid "graphCid")
        bytes (encode-dag-cbor body)
        cid (cidv1-dag-cbor bytes)]
    {:cid cid
     :bytes bytes
     :byte-length (count bytes)}))

;; ── Pure .cljc UTF-8 Decoding & Strict Canonical DAG-CBOR Validator/Decoder ──

(defn utf8-decode
  "Strictly decode unsigned UTF-8 byte vector `bs` to a string (handling
  supplementary planes such as U+10000 cleanly across JVM, bb, and nbb)."
  [bs]
  #?(:clj (let [arr (byte-array (count bs))]
            (dotimes [i (count bs)]
              (aset arr i (unchecked-byte (nth bs i))))
            (let [decoder (-> (java.nio.charset.StandardCharsets/UTF_8)
                              (.newDecoder)
                              (.onMalformedInput java.nio.charset.CodingErrorAction/REPORT)
                              (.onUnmappableCharacter java.nio.charset.CodingErrorAction/REPORT))]
              (try
                (.toString (.decode decoder (java.nio.ByteBuffer/wrap arr)))
                (catch java.nio.charset.CharacterCodingException _
                  (v/fail! :dag-cbor-invalid-utf8 "invalid UTF-8 bytes in DAG-CBOR text string" {})))))
     :cljs (let [n (count bs)
                 out (transient [])]
             (loop [i 0
                    acc out]
               (if (= i n)
                 (apply str (persistent! acc))
                 (let [b0 (nth bs i)]
                   (cond
                     (< b0 0x80)
                     (recur (inc i) (conj! acc (js/String.fromCharCode b0)))

                     (and (<= 0xc2 b0 0xdf) (< (inc i) n))
                     (let [b1 (nth bs (inc i))]
                       (when-not (= 0x80 (bit-and b1 0xc0))
                         (v/fail! :dag-cbor-invalid-utf8 "invalid 2-byte UTF-8 sequence" {:offset i}))
                       (let [cp (bit-or (bit-shift-left (bit-and b0 0x1f) 6)
                                        (bit-and b1 0x3f))]
                         (recur (+ i 2) (conj! acc (js/String.fromCodePoint cp)))))

                     (and (<= 0xe0 b0 0xef) (< (+ i 2) n))
                     (let [b1 (nth bs (+ i 1))
                           b2 (nth bs (+ i 2))]
                       (when-not (and (= 0x80 (bit-and b1 0xc0))
                                      (= 0x80 (bit-and b2 0xc0)))
                         (v/fail! :dag-cbor-invalid-utf8 "invalid 3-byte UTF-8 sequence" {:offset i}))
                       (let [cp (bit-or (bit-shift-left (bit-and b0 0x0f) 12)
                                        (bit-shift-left (bit-and b1 0x3f) 6)
                                        (bit-and b2 0x3f))]
                         (when (or (< cp 0x800) (<= 0xd800 cp 0xdfff))
                           (v/fail! :dag-cbor-invalid-utf8 "overlong or surrogate UTF-8 sequence" {:offset i}))
                         (recur (+ i 3) (conj! acc (js/String.fromCodePoint cp)))))

                     (and (<= 0xf0 b0 0xf4) (< (+ i 3) n))
                     (let [b1 (nth bs (+ i 1))
                           b2 (nth bs (+ i 2))
                           b3 (nth bs (+ i 3))]
                       (when-not (and (= 0x80 (bit-and b1 0xc0))
                                      (= 0x80 (bit-and b2 0xc0))
                                      (= 0x80 (bit-and b3 0xc0)))
                         (v/fail! :dag-cbor-invalid-utf8 "invalid 4-byte UTF-8 sequence" {:offset i}))
                       (let [cp (bit-or (bit-shift-left (bit-and b0 0x07) 18)
                                        (bit-shift-left (bit-and b1 0x3f) 12)
                                        (bit-shift-left (bit-and b2 0x3f) 6)
                                        (bit-and b3 0x3f))]
                         (when (or (< cp 0x10000) (> cp 0x10ffff))
                           (v/fail! :dag-cbor-invalid-utf8 "out-of-range 4-byte UTF-8 sequence" {:offset i}))
                         (recur (+ i 4) (conj! acc (js/String.fromCodePoint cp)))))

                     :else
                     (v/fail! :dag-cbor-invalid-utf8 "malformed UTF-8 byte sequence" {:offset i :byte b0}))))))))

(defn- read-cbor-arg [bs offset ai]
  (let [n (count bs)]
    (cond
      (< ai 24)
      [ai offset]

      (= ai 24)
      (do
        (when (>= offset n) (v/fail! :dag-cbor-truncated "truncated 1-byte CBOR argument" {:offset offset}))
        (let [val (nth bs offset)]
          (when (< val 24)
            (v/fail! :dag-cbor-non-canonical-int "non-minimal 1-byte CBOR integer" {:offset offset :value val}))
          [val (inc offset)]))

      (= ai 25)
      (do
        (when (> (+ offset 2) n) (v/fail! :dag-cbor-truncated "truncated 2-byte CBOR argument" {:offset offset}))
        (let [val (bit-or (bit-shift-left (nth bs offset) 8)
                          (nth bs (inc offset)))]
          (when (< val 0x100)
            (v/fail! :dag-cbor-non-canonical-int "non-minimal 2-byte CBOR integer" {:offset offset :value val}))
          [val (+ offset 2)]))

      (= ai 26)
      (do
        (when (> (+ offset 4) n) (v/fail! :dag-cbor-truncated "truncated 4-byte CBOR argument" {:offset offset}))
        (let [val (+ (* (nth bs offset) 16777216)
                     (* (nth bs (+ offset 1)) 65536)
                     (* (nth bs (+ offset 2)) 256)
                     (nth bs (+ offset 3)))]
          (when (< val 0x10000)
            (v/fail! :dag-cbor-non-canonical-int "non-minimal 4-byte CBOR integer" {:offset offset :value val}))
          [val (+ offset 4)]))

      (= ai 27)
      (do
        (when (> (+ offset 8) n) (v/fail! :dag-cbor-truncated "truncated 8-byte CBOR argument" {:offset offset}))
        (let [hi (+ (* (nth bs offset) 16777216)
                    (* (nth bs (+ offset 1)) 65536)
                    (* (nth bs (+ offset 2)) 256)
                    (nth bs (+ offset 3)))
              lo (+ (* (nth bs (+ offset 4)) 16777216)
                    (* (nth bs (+ offset 5)) 65536)
                    (* (nth bs (+ offset 6)) 256)
                    (nth bs (+ offset 7)))
              val (+ (* hi 4294967296) lo)]
          (when (< val 0x100000000)
            (v/fail! :dag-cbor-non-canonical-int "non-minimal 8-byte CBOR integer" {:offset offset :value val}))
          [val (+ offset 8)]))

      (= ai 31)
      (v/fail! :dag-cbor-indefinite-length "DAG-CBOR forbids indefinite-length items" {:offset offset})

      :else
      (v/fail! :dag-cbor-invalid-additional-info "invalid CBOR additional info" {:offset offset :ai ai}))))

(defn- decode-cbor-item [bs offset depth]
  (when (> depth 64)
    (v/fail! :max-depth-exceeded "DAG-CBOR decoding depth exceeded 64" {:depth depth}))
  (when (>= offset (count bs))
    (v/fail! :dag-cbor-truncated "unexpected end of DAG-CBOR input" {:offset offset}))
  (let [head (nth bs offset)
        major (unsigned-bit-shift-right head 5)
        ai (bit-and head 0x1f)
        pos (inc offset)]
    (case major
      ;; 0: unsigned int
      0
      (let [[val next-off] (read-cbor-arg bs pos ai)]
        [val next-off nil])

      ;; 1: negative int
      1
      (let [[val next-off] (read-cbor-arg bs pos ai)]
        [(- -1 val) next-off nil])

      ;; 2: byte string
      2
      (let [[len next-off] (read-cbor-arg bs pos ai)
            end (+ next-off len)]
        (when (> end (count bs))
          (v/fail! :dag-cbor-truncated "truncated CBOR byte string" {:offset next-off :length len}))
        [(subvec bs next-off end) end nil])

      ;; 3: UTF-8 text string
      3
      (let [[len next-off] (read-cbor-arg bs pos ai)
            end (+ next-off len)]
        (when (> end (count bs))
          (v/fail! :dag-cbor-truncated "truncated CBOR text string" {:offset next-off :length len}))
        [(utf8-decode (subvec bs next-off end)) end nil])

      ;; 4: array
      4
      (let [[len next-off] (read-cbor-arg bs pos ai)]
        (loop [i 0
               off next-off
               acc (transient [])]
          (if (= i len)
            [(persistent! acc) off nil]
            (let [[item n-off _] (decode-cbor-item bs off (inc depth))]
              (recur (inc i) n-off (conj! acc item))))))

      ;; 5: map (strict canonical UTF-8 byte-length then unsigned bytewise key ordering)
      5
      (let [[len next-off] (read-cbor-arg bs pos ai)]
        (loop [i 0
               off next-off
               prev-key-bytes nil
               key-order (transient [])
               entries (transient [])]
          (if (= i len)
            (let [ks (persistent! key-order)
                  es (persistent! entries)]
              [(into {} es) off ks])
            (do
              (when (>= off (count bs))
                (v/fail! :dag-cbor-truncated "truncated CBOR map key" {:offset off}))
              (let [kh (nth bs off)
                    kmaj (unsigned-bit-shift-right kh 5)
                    kai (bit-and kh 0x1f)]
                (when-not (= kmaj 3)
                  (v/fail! :dag-cbor-invalid-key "DAG-CBOR map keys must be UTF-8 text strings" {:offset off :major kmaj}))
                (let [[klen koff] (read-cbor-arg bs (inc off) kai)
                      kend (+ koff klen)]
                  (when (> kend (count bs))
                    (v/fail! :dag-cbor-truncated "truncated CBOR map key bytes" {:offset koff :length klen}))
                  (let [kbytes (subvec bs koff kend)
                        kstr (utf8-decode kbytes)]
                    (when prev-key-bytes
                      (let [cmp (compare-byte-vecs prev-key-bytes kbytes)]
                        (cond
                          (zero? cmp)
                          (v/fail! :dag-cbor-duplicate-key
                                   (str "duplicate DAG-CBOR map key: " kstr)
                                   {:key kstr :offset off})

                          (pos? cmp)
                          (v/fail! :map-keys-not-sorted
                                   (str "DAG-CBOR map keys not in canonical UTF-8 byte-length/bytewise order at key: " (pr-str kstr))
                                   {:key kstr :offset off}))))
                    (let [[vval voff _] (decode-cbor-item bs kend (inc depth))]
                      (recur (inc i) voff kbytes (conj! key-order kstr) (conj! entries [kstr vval]))))))))))

      ;; 6: tag (only tag 42 for IPLD CIDv1 link)
      6
      (let [[tag next-off] (read-cbor-arg bs pos ai)]
        (when-not (= tag 42)
          (v/fail! :dag-cbor-unsupported-tag (str "DAG-CBOR only permits tag 42, got: " tag) {:tag tag}))
        (let [[payload end _] (decode-cbor-item bs next-off (inc depth))]
          (when-not (and (vector? payload) (pos? (count payload)) (= 0 (first payload)))
            (v/fail! :dag-cbor-invalid-link "tag 42 payload must be a byte string prefixed with 0x00" {}))
          (let [cid-str (str "b" (v/base32-encode (subvec payload 1)))]
            [(v/ipld-link cid-str) end nil])))

      ;; 7: simple values (floats forbidden in KotobaSpec v1.0/v1.0.1)
      7
      (case ai
        20 [false pos nil]
        21 [true pos nil]
        22 [nil pos nil]
        (v/fail! :dag-cbor-unsupported-simple
                 (str "DAG-CBOR forbids floats and unsupported simple value ai=" ai)
                 {:ai ai :offset offset})))))

(defn decode-dag-cbor
  "Strictly validate and decode canonical DAG-CBOR unsigned byte vector `cbor-bytes`.
  Enforces canonical minimal integer encoding, valid UTF-8, and canonical DAG-CBOR
  map key order (UTF-8 byte length ascending, then unsigned UTF-8 bytewise ascending;
  rejects non-canonical UTF-16 order with `:map-keys-not-sorted`).
  Returns `{:value <decoded> :root-keys <vec-or-nil>}`."
  [cbor-bytes]
  (when-not (and (sequential? cbor-bytes) (every? #(and (integer? %) (<= 0 % 255)) cbor-bytes))
    (v/fail! :dag-cbor-invalid-bytes "expected sequence of unsigned bytes (0..255)" {}))
  (let [bs (vec cbor-bytes)
        [val end-off root-keys] (decode-cbor-item bs 0 0)]
    (when-not (= end-off (count bs))
      (v/fail! :dag-cbor-trailing-bytes
               (str "trailing bytes after DAG-CBOR root item: " (- (count bs) end-off))
               {:consumed end-off :total (count bs)}))
    {:value val
     :root-keys root-keys}))

(defn validate-dag-cbor!
  "Strictly validate canonical DAG-CBOR byte vector `cbor-bytes`. Returns `:ok`
  when canonical; throws `ex-info` (e.g. `:reason :map-keys-not-sorted`) on violation."
  [cbor-bytes]
  (decode-dag-cbor cbor-bytes)
  :ok)

(defn validate-dag-cbor
  "Validate canonical DAG-CBOR byte vector `cbor-bytes`. Returns `nil` when valid,
  or the failure reason keyword (e.g. `:map-keys-not-sorted`) when invalid."
  [cbor-bytes]
  (try
    (validate-dag-cbor! cbor-bytes)
    nil
    (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) e
      (:reason (ex-data e)))))
