(ns opcua.builtin
  "OPC UA's built-in type binary encoding — IEC 62541-6 (Part 6) §5.2.

  **OPC UA is little-endian throughout.** BACnet (`org-bacnet`, this
  workspace's other new protocol library) is big-endian throughout. A codec
  ported between the two by habit gets every multi-byte field backwards —
  worth saying plainly once, here, since it is the first thing this
  namespace does differently from `bacnet.npdu`.

  BuiltInType ids (Part 6 Table 1) implemented in this namespace: Boolean=1
  SByte=2 Byte=3 Int16=4 UInt16=5 Int32=6 UInt32=7 Int64=8 UInt64=9 Float=10
  Double=11 String=12 DateTime=13 Guid=14 ByteString=15 XmlElement=16
  StatusCode=19 QualifiedName=20 LocalizedText=21. NodeId=17/
  ExpandedNodeId=18 live in `opcua.nodeid` (their four encoding forms are
  substantial enough to earn their own namespace); Variant=24/
  ExtensionObject=22/DataValue=23 live in `opcua.variant` since they are
  built out of everything else here. DiagnosticInfo=25 is not implemented —
  see the README.

  **The -1 null convention.** String and ByteString both start with an
  Int32 length prefix. A present-but-empty value is length 0 followed by
  zero bytes; an ABSENT value is length -1 (0xFFFFFFFF on the wire) followed
  by NO bytes at all — not length 0. Collapsing 'empty' and 'null' into the
  same length-0 encoding is the classic mistake, and it is silent: a
  decoder that treats length 0 as null and length -1 as 'somehow negative,
  clamp to empty' both produce a plausible-looking string where the wire
  said something more specific.

  **Int32/UInt32 share the JS-signed-32-bit trap `bacnet.tags` documents**
  for BACnetObjectIdentifier, from the opposite direction: OPC UA puts the
  LEAST significant byte first (little-endian) instead of BACnet's most-
  significant-first, but reconstructing a value >= 0x80000000 by
  accumulating bytes through `bit-shift-left`/`bit-or` still produces a
  32-bit pattern that ClojureScript (JavaScript's 32-bit *signed* bitwise
  ops) prints negative and the JVM (64-bit longs) prints positive. Every
  UInt32 decoder here finishes with `unsigned-bit-shift-right … 0` — the
  `x >>> 0` idiom — to force the unsigned reading on both platforms; see
  `decode-uint32`'s docstring for the worked failure.

  **Int64/UInt64 are NOT plain numbers here.** A 100-nanosecond DateTime
  tick count reaches roughly 1.3×10^17 for a present-day timestamp — past
  2^53 (9007199254740992), the largest integer a JavaScript `number` (an
  IEEE-754 double) represents exactly. Returning such a value as a single
  number would silently round it on the ClojureScript path while looking
  exact on the JVM (64-bit `long`), the same 'looks right on one platform'
  failure shape as the UInt32 case, just past the point where `unsigned-
  bit-shift-right` alone can fix it — a 64-bit quantity does not fit a
  32-bit shift's guarantee. So Int64/UInt64/DateTime are represented as
  `{:low u32 :high u32}` word pairs: exact on both platforms, because
  every operation on them is a 32-bit `bit-and`/`bit-or`/`bit-shift-left`/
  `unsigned-bit-shift-right` on one word at a time, never arithmetic on a
  value that might exceed 2^53.

  **Float/Double bit-reinterpretation uses the host platform's own IEEE-754
  primitives** (`Float/floatToRawIntBits`+`intBitsToFloat` /
  `Double/doubleToRawLongBits`+`longBitsToDouble` on the JVM; `DataView` on
  ClojureScript) rather than a hand-rolled bit-level IEEE-754 encoder —
  reimplementing IEEE-754 rounding and NaN/subnormal handling from memory
  is exactly the kind of 'confidently wrong' code this library's own
  reference style warns against building test vectors out of. What crosses
  the wire as bytes is still assembled and read with this namespace's own
  `bit-and`/`bit-shift-left`/`unsigned-bit-shift-right` little-endian
  helpers; only the 32/64-bit-integer <-> float/double reinterpretation
  step borrows the platform's ALU instead of re-deriving it.")

(defn u8 [n] (bit-and n 0xFF))

;; ── little-endian byte helpers ────────────────────────────────────────

(defn le16 [n] [(u8 n) (u8 (unsigned-bit-shift-right n 8))])
(defn le32 [n] [(u8 n) (u8 (unsigned-bit-shift-right n 8))
                (u8 (unsigned-bit-shift-right n 16)) (u8 (unsigned-bit-shift-right n 24))])

(defn safe-nth [bs i] (when (< i (count bs)) (nth bs i)))

(defn rd-le16 [bs offset]
  (let [b0 (safe-nth bs offset) b1 (safe-nth bs (inc offset))]
    (when (and b0 b1) (bit-or (bit-and b0 0xFF) (bit-shift-left (bit-and b1 0xFF) 8)))))

(defn rd-le32-raw
  "Reads 4 little-endian bytes into a 32-bit *pattern* — sign is whatever
  the platform's bit-or leaves it as. Callers wanting the unsigned reading
  use `decode-uint32`; callers wanting signed use `decode-int32`."
  [bs offset]
  (let [b0 (safe-nth bs offset) b1 (safe-nth bs (+ offset 1))
        b2 (safe-nth bs (+ offset 2)) b3 (safe-nth bs (+ offset 3))]
    (when (and b0 b1 b2 b3)
      (bit-or (bit-and b0 0xFF) (bit-shift-left (bit-and b1 0xFF) 8)
              (bit-shift-left (bit-and b2 0xFF) 16) (bit-shift-left (bit-and b3 0xFF) 24)))))

;; ── Boolean (§5.2.1) ─────────────────────────────────────────────────────

(defn encode-boolean [b] [(if b 1 0)])
(defn decode-boolean [bs offset]
  (if-let [b (safe-nth bs offset)]
    {:status :ok :value (not (zero? b)) :next (inc offset)}
    [:error :opcua/truncated]))

;; ── SByte / Byte (§5.2.2 / §5.2.3) ───────────────────────────────────────

(defn encode-byte [n] [(u8 n)])
(defn decode-byte [bs offset]
  (if-let [b (safe-nth bs offset)]
    {:status :ok :value (bit-and b 0xFF) :next (inc offset)}
    [:error :opcua/truncated]))

(defn encode-sbyte [n] [(u8 n)])
(defn decode-sbyte [bs offset]
  (if-let [b (safe-nth bs offset)]
    {:status :ok :value (if (>= b 0x80) (- b 0x100) b) :next (inc offset)}
    [:error :opcua/truncated]))

;; ── Int16 / UInt16 (§5.2.4 / §5.2.5) ──────────────────────────────────────

(defn encode-uint16 [n] (le16 n))
(defn decode-uint16 [bs offset]
  (if-let [v (rd-le16 bs offset)]
    {:status :ok :value (bit-and v 0xFFFF) :next (+ offset 2)}
    [:error :opcua/truncated]))

(defn encode-int16 [n] (le16 (bit-and n 0xFFFF)))
(defn decode-int16 [bs offset]
  (if-let [v (rd-le16 bs offset)]
    (let [v (bit-and v 0xFFFF)]
      {:status :ok :value (if (>= v 0x8000) (- v 0x10000) v) :next (+ offset 2)})
    [:error :opcua/truncated]))

;; ── Int32 / UInt32 (§5.2.6 / §5.2.7) ──────────────────────────────────────

(defn encode-uint32 [n] (le32 n))

(defn decode-uint32
  "Reads a little-endian UInt32 and finishes with `unsigned-bit-shift-right
  … 0` — without it, `decode-uint32` of the bytes for 3000000000 comes back
  as -1294967296 on the ClojureScript path (JS `bit-or` is 32-bit signed)
  and the correct 3000000000 on the JVM (64-bit `long`), so a JVM-only test
  suite passes while the browser silently gets a negative StatusCode /
  SecureChannelId / message size. This is the accumulation half of the
  trap `bacnet.tags/decode-unsigned-value` documents for the same reason."
  [bs offset]
  (if-let [raw (rd-le32-raw bs offset)]
    {:status :ok :value (unsigned-bit-shift-right raw 0) :next (+ offset 4)}
    [:error :opcua/truncated]))

(defn encode-int32 [n] (le32 (if (neg? n) (+ n 0x100000000) n)))

(defn decode-int32
  "Deliberately built on `decode-uint32` rather than trusting the raw
  `bit-or` result's own sign: on ClojureScript, JS's `bit-or` coerces its
  operands through ToInt32, so a value with bit 31 set genuinely comes back
  as a negative JS number for free — but on the JVM, `bit-or` on the longs
  this namespace uses never overflows 32 bits, so the same bit pattern
  comes back as an ordinary *positive* long (4294967295, not -1). Relying
  on 'the bitwise op already signs it' is correct on exactly one of the
  two platforms; going through the always-unsigned `decode-uint32` and then
  applying the two's-complement correction with ordinary arithmetic
  (subtracting 2^32 when the unsigned value is >= 2^31) gives the same
  answer on both."
  [bs offset]
  (let [u (decode-uint32 bs offset)]
    (if (= :error (first u)) u
        (let [v (:value u)]
          {:status :ok :value (if (>= v 0x80000000) (- v 0x100000000) v) :next (:next u)}))))

;; ── Int64 / UInt64 (§5.2.8 / §5.2.9) — {:low u32 :high u32} word pairs ────
;; See namespace docstring for why a plain number is not used.

(defn encode-uint64 [{:keys [low high]}] (into (le32 low) (le32 high)))
(defn decode-uint64 [bs offset]
  (let [lo (decode-uint32 bs offset) hi (decode-uint32 bs (+ offset 4))]
    (cond (= :error (first lo)) lo
          (= :error (first hi)) hi
          :else {:status :ok :value {:low (:value lo) :high (:value hi)} :next (+ offset 8)})))

(def encode-int64
  "Same wire shape as UInt64 — two's-complement is a bit pattern, not a
  different byte layout. Sign lives entirely in the high word."
  encode-uint64)
(def decode-int64 decode-uint64)

(defn int64-negative? [{:keys [high]}] (>= high 0x80000000))

(defn zero-word-pair [] {:low 0 :high 0})

;; ── Float / Double (§5.2.10 / §5.2.11) ────────────────────────────────────
;; See namespace docstring — bit reinterpretation borrows the platform ALU.

#?(:clj
   (defn encode-float [f] (encode-int32 (Float/floatToRawIntBits (float f))))
   :cljs
   (defn encode-float [f]
     (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
       (.setFloat32 dv 0 f true)
       (vec (js/Uint8Array. buf)))))

#?(:clj
   (defn decode-float [bs offset]
     (let [r (decode-int32 bs offset)]
       (if (= :error (first r)) r
           {:status :ok :value (Float/intBitsToFloat (:value r)) :next (:next r)})))
   :cljs
   (defn decode-float [bs offset]
     (if (< (+ offset 4) (inc (count bs)))
       (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
         (dotimes [i 4] (.setUint8 dv i (nth bs (+ offset i))))
         {:status :ok :value (.getFloat32 dv 0 true) :next (+ offset 4)})
       [:error :opcua/truncated])))

#?(:clj
   (defn encode-double [f]
     (let [bits (Double/doubleToRawLongBits (double f))]
       (into (le32 (unchecked-int bits)) (le32 (unchecked-int (bit-shift-right bits 32))))))
   :cljs
   (defn encode-double [f]
     (let [buf (js/ArrayBuffer. 8) dv (js/DataView. buf)]
       (.setFloat64 dv 0 f true)
       (vec (js/Uint8Array. buf)))))

#?(:clj
   (defn decode-double [bs offset]
     (let [lo (decode-int32 bs offset) hi (decode-int32 bs (+ offset 4))]
       (if (or (= :error (first lo)) (= :error (first hi)))
         [:error :opcua/truncated]
         {:status :ok
          :value (Double/longBitsToDouble
                  (bit-or (bit-and (long (:value lo)) 0xFFFFFFFF)
                          (bit-shift-left (long (:value hi)) 32)))
          :next (+ offset 8)})))
   :cljs
   (defn decode-double [bs offset]
     (if (< (+ offset 8) (inc (count bs)))
       (let [buf (js/ArrayBuffer. 8) dv (js/DataView. buf)]
         (dotimes [i 8] (.setUint8 dv i (nth bs (+ offset i))))
         {:status :ok :value (.getFloat64 dv 0 true) :next (+ offset 8)})
       [:error :opcua/truncated])))

;; ── UTF-8 <-> bytes ────────────────────────────────────────────────────
;; `(map int some-string)` gives JVM code points and ClojureScript ZEROES
;; (a cljs character is a one-character string; `int` of a string is not a
;; code point) — `org-modbus`'s README documents this exact trap costing it
;; a silent test-suite hole. Using the platform's real UTF-8 encoder here
;; instead of any char-by-char mapping is not a style preference.

#?(:clj
   (defn- utf8-encode [s] (vec (.getBytes ^String s "UTF-8")))
   :cljs
   (defn- utf8-encode [s] (vec (.encode (js/TextEncoder.) s))))

#?(:clj
   (defn- utf8-decode [bs]
     (String. (byte-array (map unchecked-byte bs)) "UTF-8"))
   :cljs
   (defn- utf8-decode [bs]
     (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js bs)))))

;; ── String (§5.2.12) — and ByteString (§5.2.15) share this length-prefix ──

(defn encode-string
  "`nil` -> the -1 null encoding (4 bytes, no payload). `\"\"` -> length 0,
  zero payload bytes. These are two different wire values, not one."
  [s]
  (if (nil? s)
    (encode-int32 -1)
    (let [bs (utf8-encode s)]
      (into (encode-int32 (count bs)) bs))))

(defn decode-string [bs offset]
  (let [len-r (decode-int32 bs offset)]
    (if (= :error (first len-r)) len-r
        (let [len (:value len-r) body-start (:next len-r)]
          (cond
            (= len -1) {:status :ok :value nil :next body-start}
            (neg? len) [:error :opcua/negative-length]
            (> (+ body-start len) (count bs)) [:error :opcua/truncated]
            :else {:status :ok :value (utf8-decode (subvec (vec bs) body-start (+ body-start len)))
                   :next (+ body-start len)})))))

(defn encode-byte-string
  [bs]
  (if (nil? bs)
    (encode-int32 -1)
    (into (encode-int32 (count bs)) bs)))

(defn decode-byte-string [bs offset]
  (let [len-r (decode-int32 bs offset)]
    (if (= :error (first len-r)) len-r
        (let [len (:value len-r) body-start (:next len-r)]
          (cond
            (= len -1) {:status :ok :value nil :next body-start}
            (neg? len) [:error :opcua/negative-length]
            (> (+ body-start len) (count bs)) [:error :opcua/truncated]
            :else {:status :ok :value (vec (subvec (vec bs) body-start (+ body-start len)))
                   :next (+ body-start len)})))))

;; XmlElement (§5.2.16) is defined by the standard as "encoded as though it
;; were a ByteString containing the UTF-8 encoded XML text" — the same
;; length-prefix, no separate shape of its own.
(def encode-xml-element encode-byte-string)
(def decode-xml-element decode-byte-string)

;; ── DateTime (§5.2.5.2 / Part 6 Table 1) ──────────────────────────────────
;; Windows FILETIME convention: 100-nanosecond intervals since
;; 1601-01-01T00:00:00Z, encoded as Int64. Represented here as the raw
;; `{:low :high}` tick pair (see namespace docstring) — this library does
;; not convert to/from a calendar date; see README's "Not here".

(def encode-date-time encode-int64)
(def decode-date-time decode-int64)

;; ── Guid (§5.2.14) ─────────────────────────────────────────────────────
;; RFC 4122 field layout, but Data1/Data2/Data3 are little-endian on the
;; wire (the opposite of the RFC's own big-endian string form) while Data4
;; is 8 raw bytes in RFC order — a Guid is the one built-in type whose
;; fields do NOT all share one endianness, which is exactly the kind of
;; thing worth stating rather than assuming.

(defn encode-guid [{:keys [data1 data2 data3 data4]}]
  (into (into (le32 data1) (le16 data2)) (into (le16 data3) data4)))

(defn decode-guid [bs offset]
  (if (> (+ offset 16) (count bs))
    [:error :opcua/truncated]
    (let [d1 (decode-uint32 bs offset)
          d2 (decode-uint16 bs (+ offset 4))
          d3 (decode-uint16 bs (+ offset 6))
          d4 (vec (subvec (vec bs) (+ offset 8) (+ offset 16)))]
      {:status :ok
       :value {:data1 (:value d1) :data2 (:value d2) :data3 (:value d3) :data4 d4}
       :next (+ offset 16)})))

;; ── StatusCode (§7.34, Table 1 entry 19) — a UInt32 with a structured top ─
;; Top 2 bits: 00 Good, 01 Uncertain, 10 Bad. Bare numeric code either way.

(def encode-status-code encode-uint32)
(def decode-status-code decode-uint32)

(defn status-severity [code]
  (case (bit-and (unsigned-bit-shift-right code 30) 0x03)
    0 :good 1 :uncertain 2 :bad 3 :bad))

;; ── QualifiedName (§7.3) ───────────────────────────────────────────────

(defn encode-qualified-name [{:keys [namespace-index name]}]
  (into (encode-uint16 namespace-index) (encode-string name)))

(defn decode-qualified-name [bs offset]
  (let [ns-r (decode-uint16 bs offset)]
    (if (= :error (first ns-r)) ns-r
        (let [name-r (decode-string bs (:next ns-r))]
          (if (= :error (first name-r)) name-r
              {:status :ok
               :value {:namespace-index (:value ns-r) :name (:value name-r)}
               :next (:next name-r)})))))

;; ── LocalizedText (§7.5) ───────────────────────────────────────────────
;; An encoding-mask byte (bit0 = locale present, bit1 = text present),
;; NOT a fixed two-field struct — a LocalizedText with only a Text and no
;; Locale is one byte shorter than one with both, and a decoder that
;; assumes both fields are always present misreads everything after it.

(defn encode-localized-text [{:keys [locale text]}]
  (let [mask (bit-or (if locale 0x01 0x00) (if text 0x02 0x00))]
    (into [mask] (concat (when locale (encode-string locale)) (when text (encode-string text))))))

(defn decode-localized-text [bs offset]
  (if-let [mask (safe-nth bs offset)]
    (let [has-locale? (bit-test mask 0) has-text? (bit-test mask 1)
          after-mask (inc offset)]
      (let [locale-r (if has-locale? (decode-string bs after-mask) {:status :ok :value nil :next after-mask})]
        (if (= :error (first locale-r)) locale-r
            (let [text-r (if has-text? (decode-string bs (:next locale-r))
                             {:status :ok :value nil :next (:next locale-r)})]
              (if (= :error (first text-r)) text-r
                  {:status :ok
                   :value {:locale (:value locale-r) :text (:value text-r)}
                   :next (:next text-r)})))))
    [:error :opcua/truncated]))
