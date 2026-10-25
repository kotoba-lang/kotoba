(ns protobuf.wire
  "Protocol Buffers **wire format** (protobuf.dev, \"Encoding\") — encode and
  decode, schema-driven, in portable `.cljc` with no dependencies and no code
  generation.

  Deliberately *only* the wire format. There is no `.proto` parser, no
  descriptor set, no generated classes. A schema here is an ordinary EDN map
  from field number to a small descriptor:

      {1 {:name :value    :type :bytes}
       5 {:name :sequence :type :uint64}
       9 {:name :data     :type :bytes}}

  That is enough for the two things this workspace needs protobuf for — IPNS
  records and Kademlia DHT messages — and it keeps the schema reviewable next
  to the spec it came from rather than hidden in generated output.

  ## Unknown fields are preserved, byte-for-byte

  The rule that makes or breaks this library. Protobuf is designed so a reader
  can skip fields it does not know, and every real deployment relies on it: a
  record written by a newer Kubo carries fields this schema has never heard of.

  A decoder that drops them and an encoder that cannot put them back means a
  record **cannot round-trip** — and for a *signed* record that is not a
  compatibility inconvenience, it is a validation failure. The signature covers
  bytes that no longer exist. So `decode` keeps unknown fields as raw
  `{:field-number [wire-type octets]}` under `:protobuf/unknown`, and `encode`
  re-emits them in field-number order alongside the known ones.

  This is the same lesson as `dnssec.canonical`: what breaks is never the
  arithmetic, it is that two sides serialized the same value differently.

  ## Encoding is deterministic

  The spec permits fields in any order and does not require a canonical form.
  This library always emits ascending field number, and never emits an absent
  or default-valued optional field. Determinism is not aesthetic here — a
  signature is over bytes, and \"the same message\" has to mean the same
  octets on every host and every run."
  (:require [kotoba.lang.text :as str]))

;; ── wire types (protobuf.dev, Encoding §Message Structure) ────────────────

(def ^:const wt-varint 0)
(def ^:const wt-fixed64 1)
(def ^:const wt-length 2)
(def ^:const wt-fixed32 5)

(def type->wire
  "Field type → wire type. Groups (wire types 3 and 4) are deprecated and
  absent: a message using them is from before proto2's own deprecation and is
  not something this workspace will meet."
  {:int32 wt-varint :int64 wt-varint :uint32 wt-varint :uint64 wt-varint
   :sint32 wt-varint :sint64 wt-varint :bool wt-varint :enum wt-varint
   :fixed64 wt-fixed64 :sfixed64 wt-fixed64 :double wt-fixed64
   :fixed32 wt-fixed32 :sfixed32 wt-fixed32 :float wt-fixed32
   :bytes wt-length :string wt-length :message wt-length})

;; ── varint ────────────────────────────────────────────────────────────────

;; Range note. Varints are computed with the host's ordinary integers: a 64-bit
;; long on the JVM, exact for the whole protobuf range; a double on
;; ClojureScript, exact only to 2^53. A library reaching for BigInt would be
;; non-portable (`bigint` is JVM-only, goog.math.Long is CLJS-only), so the
;; edge stays where the double is.
;;
;; This note used to say the fields here "stay far inside that" and name an
;; IPNS TTL as an example. **Measured 2026-08-17, that was wrong**, and the
;; bound it pointed at was enforced nowhere:
;;
;;   bytes for 2^53+1   -> JVM 9007199254740993   CLJS 9007199254740992
;;   bytes for 2^63-1   -> JVM 9223372036854775807 CLJS 9223372036854776000
;;
;; Returned as ordinary values, with no error, so the same octets decoded to
;; different numbers on the two hosts. And the example was the counterexample:
;; an IPNS TTL is in NANOSECONDS, 2^53 ns is 104 days, and a record with a
;; one-year TTL is an ordinary record, not a hostile one.
;;
;; So the bound is enforced now, in both directions and on both hosts, for the
;; reason `encode-varint` already gives about negatives: a value one host
;; accepts and the other silently corrupts is worse than a value neither
;; accepts. A caller that genuinely needs the top eleven bits of a uint64 must
;; read the field's raw octets -- this is the place that would have to grow a
;; big-integer path, and that is a decision with a cost, not an oversight.

(def ^:const max-exact
  "Largest integer both hosts represent exactly, 2^53-1.

  The same value `proto.wire/max-exact` uses. The two libraries decode the
  same wire format and MUST agree about which values exist; when this said
  2^53 and enforced nothing, they disagreed on every value above the edge."
  9007199254740991)

(defn encode-varint
  "Base-128 varint, little-endian groups, high bit as continuation.

  Negative values encode as their two's-complement 64-bit pattern, which is why
  a negative `int32` takes ten octets on the wire — a protobuf quirk rather
  than a bug here. `sint32`/`sint64` exist precisely to avoid it and go through
  `zigzag` first.

  **A negative value is refused**, on both hosts, and this is a deliberate
  limitation rather than an oversight. Encoding one requires the full unsigned
  64-bit pattern (ten groups); decoding one requires a value above
  `Long/MAX_VALUE` on the JVM and above 2^53 on ClojureScript. Supporting it
  would mean a big-integer path on both sides for a case no schema here has —
  IPNS and Kademlia are `uint64`, `bytes` and `enum` throughout — and a
  half-supported signed path is worse than none, because it would encode on one
  host and fail to decode on the other. `sint32`/`sint64` carry signed values
  correctly through `zigzag` and cost one octet for small negatives.

  `decode-varint` refuses past nine groups for the same reason, so the two
  directions agree about exactly which values exist."
  [n]
  (cond
    (neg? n)
    (throw (ex-info "negative varints are not supported; declare the field as sint32/sint64 so it is zigzag-encoded"
                    {:value n}))

    ;; Past the edge the arithmetic below is already inexact on ClojureScript,
    ;; so the octets emitted would be the octets of a DIFFERENT number -- and
    ;; the caller would have no way to know, because `quot` and `mod` do not
    ;; complain. Refused rather than emitted for the same reason negatives are.
    (> n max-exact)
    (throw (ex-info "varint exceeds the exactly-representable integer range; the octets would encode a different number on ClojureScript"
                    {:value n :max-exact max-exact}))

    :else
    (loop [v n out []]
      (let [b (mod v 128)
            v' (quot v 128)]
        (if (zero? v')
          (conj out b)
          (recur v' (conj out (bit-or b 0x80))))))))

(defn decode-varint
  "Read a varint at `i`. Returns `[value next-index]`.

  Refuses past **nine** groups. Nine groups carry 63 bits, which covers every
  value this library can also encode (see `encode-varint`: negatives, the only
  values needing a tenth group, are refused). An unterminated run is also how a
  malformed or hostile message turns a decoder into an unbounded loop, and the
  same guard stops both — checked before the multiplier grows, so the overflow
  never happens either."
  [bs i]
  (loop [i i mult 1 acc 0 n 0]
    (when (>= i (count bs))
      (throw (ex-info "truncated varint" {:at i})))
    (when (>= n 9)
      (throw (ex-info "varint longer than 9 groups; a signed 64-bit value needs ten and is not supported (declare the field sint32/sint64)"
                      {:at i})))
    (let [b (bit-and (nth bs i) 0xFF)
          acc (+ acc (* mult (bit-and b 0x7F)))]
      ;; Checked as it accumulates, not at the end: on ClojureScript an `acc`
      ;; past the edge is already the wrong number, and comparing it is the
      ;; only thing left that is still reliable about it.
      (when (> acc max-exact)
        (throw (ex-info "varint exceeds the exactly-representable integer range; read the field's raw octets if the full uint64 range is needed"
                        {:at i :max-exact max-exact})))
      (if (zero? (bit-and b 0x80))
        [acc (inc i)]
        ;; 128^9 is exactly Long/MAX+1, so the multiplier must not be advanced
        ;; on the step that the guard above is about to reject — otherwise the
        ;; overflow happens before the refusal does.
        (recur (inc i) (if (>= (inc n) 9) mult (* mult 128)) acc (inc n))))))

(defn zigzag
  "sint encoding: map signed to unsigned so small negatives stay small
  (`-1 → 1`, `1 → 2`). Without it every negative number costs ten octets."
  [n]
  (if (neg? n) (dec (* -2 n)) (* 2 n)))

(defn un-zigzag [n]
  (let [n (long n)]
    (if (odd? n) (- (quot (inc n) 2)) (quot n 2))))

;; ── fixed width ───────────────────────────────────────────────────────────

;; Arithmetic, not bit shifts, for the reason the varint path gives: on
;; ClojureScript `bit-shift-left` / `bit-shift-right` operate on int32 AND take
;; their shift count modulo 32. Both halves of that bit.
;;
;; Measured 2026-08-17, with the shift version: encoding 255 as a `fixed64`
;; emitted `[255 0 0 0 255 0 0 0]` -- the shifts for bytes 4..7 wrapped to
;; 0,8,16,24 and re-emitted the low four -- and decoding those octets returned
;; 510. The JVM, whose shifts are 64-bit, was correct throughout, so a fixed64
;; written in a Worker and read on the JVM was a different number, silently.
;; A `fixed32` whose top byte was >= 0x80 came back NEGATIVE on ClojureScript
;; for the same reason (`(bit-shift-left 0xFF 24)` is -16777216 there).

(def ^:private two-pow-32 4294967296)

(defn- encode-fixed [n width]
  (let [v (cond
            ;; A negative sfixed32 is its two's-complement pattern, and 2^32
            ;; is exact on both hosts, so this one is representable.
            (and (neg? n) (= width 4)) (+ n two-pow-32)
            ;; A negative sfixed64 is not: the pattern is 2^64 - |n|, which no
            ;; double holds. Refused rather than half-supported, exactly as
            ;; `encode-varint` refuses negatives.
            (neg? n)
            (throw (ex-info "negative sfixed64 is not supported; the two's-complement pattern is past the exactly-representable range"
                            {:value n}))
            :else n)]
    (when (> v max-exact)
      (throw (ex-info "fixed field exceeds the exactly-representable integer range"
                      {:value n :width width :max-exact max-exact})))
    (loop [v v k 0 out []]
      (if (= k width)
        out
        (recur (quot v 256) (inc k) (conj out (mod v 256)))))))

(defn- decode-fixed [bs i width]
  [(loop [k 0 acc 0 mult 1]
     (if (= k width)
       acc
       (let [acc' (+ acc (* mult (bit-and (nth bs (+ i k)) 0xFF)))]
         (when (> acc' max-exact)
           (throw (ex-info "fixed field exceeds the exactly-representable integer range"
                           {:at i :width width :max-exact max-exact})))
         ;; `mult` stops growing once it is past anything `acc` may hold. Left
         ;; to multiply freely it reaches 256^8 = 2^64 on the eighth byte and
         ;; throws `long overflow` on the JVM -- while ClojureScript, whose
         ;; doubles do not overflow, sails past. Measured: this is the same
         ;; hazard `proto.wire/read-varint` documents for its shift, met a
         ;; second time in a second implementation of the same format.
         ;; Capping is safe: at that point `mult` already exceeds `max-exact`,
         ;; so any nonzero byte there trips the guard above regardless.
         (recur (inc k) acc' (if (> mult max-exact) mult (* mult 256))))))
   (+ i width)])

;; ── strings ───────────────────────────────────────────────────────────────

(defn utf8-bytes [s]
  #?(:clj (vec (.getBytes ^String s "UTF-8"))
     :cljs (vec (.encode (js/TextEncoder.) s))))

(defn utf8-string [bs]
  #?(:clj (String. (byte-array (map unchecked-byte bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js bs)))))

;; ── encode ────────────────────────────────────────────────────────────────

(declare encode decode)

(defn- tag [field-number wire-type]
  (encode-varint (bit-or (bit-shift-left field-number 3) wire-type)))

(defn- encode-value [{:keys [type schema]} v]
  (case type
    (:int32 :int64 :uint32 :uint64 :enum) (encode-varint (long v))
    (:sint32 :sint64) (encode-varint (zigzag (long v)))
    :bool (encode-varint (if v 1 0))
    (:fixed32 :sfixed32) (encode-fixed v 4)
    (:fixed64 :sfixed64) (encode-fixed v 8)
    :bytes (vec v)
    :string (utf8-bytes (str v))
    :message (encode schema v)
    (throw (ex-info "unsupported field type" {:type type}))))

(defn- encode-field [n desc v]
  (let [wt (type->wire (:type desc))
        payload (encode-value desc v)]
    (if (= wt wt-length)
      (into (into (vec (tag n wt)) (encode-varint (count payload))) payload)
      (into (vec (tag n wt)) payload))))

(defn encode
  "Message map → octet vector, fields in ascending field-number order.

  A field whose value is `nil` is omitted — protobuf has no way to say
  \"present and null\", and emitting a zero-length or zero-valued field where
  the sender had nothing is a different message. `:repeated` descriptors take a
  sequence and emit one field per element (unpacked; packed repeated scalars
  are not produced, and are accepted on decode)."
  [schema m]
  (let [unknown (:protobuf/unknown m)
        known (for [[n desc] schema
                    :let [v (get m (:name desc))]
                    :when (some? v)]
                [n (if (:repeated desc)
                     (vec (mapcat #(encode-field n desc %) v))
                     (encode-field n desc v))])
        unk (for [[n [wt octets]] unknown]
              [n (into (vec (tag n wt)) octets)])]
    (vec (mapcat second (sort-by first (concat known unk))))))

;; ── decode ────────────────────────────────────────────────────────────────

(defn- skip
  "Read the payload of a field whose type we do not know, so it can be kept
  verbatim. Returns `[octets next-index]` where `octets` is the payload only —
  the tag is reconstructed on encode from the field number and wire type."
  [bs i wt]
  (case wt
    0 (let [[_ j] (decode-varint bs i)] [(vec (subvec (vec bs) i j)) j])
    1 [(vec (subvec (vec bs) i (+ i 8))) (+ i 8)]
    5 [(vec (subvec (vec bs) i (+ i 4))) (+ i 4)]
    2 (let [[len j] (decode-varint bs i)
            end (+ j (long len))]
        [(vec (subvec (vec bs) i end)) end])
    (throw (ex-info "unknown wire type" {:wire-type wt :at i}))))

(defn- decode-value [{:keys [type schema]} bs i wt]
  (case wt
    0 (let [[v j] (decode-varint bs i)]
        [(case type
           (:sint32 :sint64) (un-zigzag v)
           :bool (not (zero? (long v)))
           (long v))
         j])
    1 (decode-fixed bs i 8)
    5 (decode-fixed bs i 4)
    2 (let [[len j] (decode-varint bs i)
            end (+ j (long len))
            payload (vec (subvec (vec bs) j end))]
        [(case type
           :string (utf8-string payload)
           :message (decode schema payload)
           payload)
         end])
    (throw (ex-info "unknown wire type" {:wire-type wt :at i}))))

(defn decode
  "Octets → message map. Unknown fields land under `:protobuf/unknown` as
  `{field-number [wire-type payload-octets]}` so `encode` can put them back.

  A field the schema knows but that arrives with the *wrong* wire type is
  treated as unknown rather than coerced: coercing would silently reinterpret
  someone else's data, and a schema mismatch is worth surfacing."
  [schema bs]
  (let [bs (vec bs)
        n (count bs)]
    (loop [i 0 out {}]
      (if (>= i n)
        out
        (let [[t j] (decode-varint bs i)
              t (long t)
              fnum (bit-shift-right t 3)
              wt (bit-and t 0x07)
              desc (get schema fnum)]
          (if (and desc (= wt (type->wire (:type desc))))
            (let [[v k] (decode-value desc bs j wt)]
              (recur k (if (:repeated desc)
                         (update out (:name desc) (fnil conj []) v)
                         (assoc out (:name desc) v))))
            (let [[payload k] (skip bs j wt)]
              (recur k (assoc-in out [:protobuf/unknown fnum] [wt payload])))))))))

(defn round-trips?
  "Does `bs` survive decode→encode unchanged? The property a signed message
  depends on, exposed so a caller can assert it on real data rather than trust
  it. Returns false rather than throwing on malformed input."
  [schema bs]
  (try (= (vec bs) (encode schema (decode schema bs)))
       (catch #?(:clj Exception :cljs :default) _ false)))

(defn hex [bs]
  (str/join " " (map #(let [s #?(:clj (Integer/toHexString (bit-and % 0xFF))
                                :cljs (.toString (bit-and % 0xFF) 16))]
                        (if (= 1 (count s)) (str "0" s) s))
                     bs)))
