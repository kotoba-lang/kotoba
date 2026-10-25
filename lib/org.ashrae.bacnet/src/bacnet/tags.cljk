(ns bacnet.tags
  "BACnet's primitive application tag encoding — ASHRAE 135 Clause 20.2.1.

  Every encoded value starts with a **tag** octet:

  ```
  bit:   7 6 5 4        3       2 1 0
         [tag number]  [class] [length/value/type]
  ```

  Tag number (bits 7-4) is 0-14 inline, or 15 (0xF) meaning 'the real tag
  number is the next octet' — the extended tag number form, needed once a
  context tag number exceeds 14 (ReadPropertyMultiple's result list nests
  well past that).

  Class (bit 3) is 0 for an **application** tag (the six-bit type comes from
  the fixed Table 20-1 vocabulary: Boolean, Unsigned, Real, ...) and 1 for a
  **context** tag, where the same tag-number slot is repurposed per-service —
  context tag 0 means 'object identifier' inside ReadProperty-Request and
  something else entirely inside another service's parameter list. A decoder
  that ignores the class bit and looks up tag numbers in one global table
  will silently misdecode context-tagged data, because the numbers collide
  by design.

  Length/Value/Type (bits 2-0), the classic source of subtle bugs:

    0-4   the data is that many bytes long (0 is legal — Null)
    5     'extended length' — a length octet follows: <254 is the length
          directly, 254 means a 2-octet big-endian length follows *that*,
          255 means a 4-octet length follows. Getting this three-level
          escalation half right — handling the 1-octet case and treating
          254/255 as ordinary lengths — is the usual mistake; it works for
          every short test string and corrupts the first long one.
    6     opening tag (context only — brackets a constructed value)
    7     closing tag (context only)

  **Boolean is the other trap.** For an *application*-tagged Boolean the
  value itself lives in the length/value/type field (0 or 1) and there are
  ZERO data octets — the encoding has already ended after the tag byte. For
  a *context*-tagged Boolean the LVT field just says 'length 1' like any
  other primitive, and the actual 0/1 lives in that one following data byte.
  Reading a context-tagged Boolean as if it were application-tagged (or vice
  versa) reads a byte that isn't there, or reads the wrong byte as the
  value — and does so silently, because both forms parse without error.

  Application tag numbers implemented here (Table 20-1): Null=0, Boolean=1,
  Unsigned=2, Signed=3 (two's-complement), Enumerated=9,
  BACnetObjectIdentifier=12. Real/Double/OctetString/CharacterString/
  BitString/Date/Time are Table 20-1 entries this library does not encode —
  see the README's 'Not here'.")

;; ── byte helpers ─────────────────────────────────────────────────────────

(defn- u8 [n] (bit-and n 0xFF))

(defn- safe-nth
  "`nth` that returns nil past the end instead of throwing — every decoder
  here treats 'ran out of bytes' as a named error, never an exception."
  [bs i]
  (when (< i (count bs)) (nth bs i)))

;; ── tag header (encode) ──────────────────────────────────────────────────

(defn- tag-number-octets
  "Tag-number portion of the tag byte plus any extended-tag-number octet.
  Tag numbers 0-14 fit in the nibble; 15 (0xF) means 'read the next octet',
  so 15 itself can never be encoded as an inline nibble even though it
  numerically fits — it is reserved as the escape."
  [tag-number]
  (if (< tag-number 15)
    {:nibble tag-number :extra []}
    {:nibble 15 :extra [(u8 tag-number)]}))

(defn encode-tag-header
  "The tag octet(s) for `tag-number`/`context?`/`lvt` (a 3-bit length/value/
  type code, 0-7), NOT including any extended-length octets that a `lvt` of
  5 implies — callers building a primitive value use `encode-length-header`
  for those. Kept separate because opening/closing tags (`lvt` 6/7) have no
  length octets at all, and folding both concerns into one function is how
  the length gets attached to the wrong branch."
  [tag-number context? lvt]
  (let [{:keys [nibble extra]} (tag-number-octets tag-number)
        b0 (bit-or (bit-shift-left nibble 4)
                    (if context? 0x08 0x00)
                    (bit-and lvt 0x07))]
    (into [b0] extra)))

(defn encode-length-header
  "The extended-length octet(s) for a data length `n` >= 5. `lvt` in the tag
  byte is fixed at 5 (the escape) and the real length follows: one octet if
  n < 254, else 254 followed by a 2-octet big-endian length, else 255
  followed by a 4-octet big-endian length. n < 5 does not use this — the
  length lives directly in the tag byte's LVT field."
  [n]
  (cond
    (< n 254) [n]
    (<= n 0xFFFF) (into [254] [(u8 (unsigned-bit-shift-right n 8)) (u8 n)])
    :else (into [255] [(u8 (unsigned-bit-shift-right n 24))
                        (u8 (unsigned-bit-shift-right n 16))
                        (u8 (unsigned-bit-shift-right n 8))
                        (u8 n)])))

(defn encode-application-tag
  "Tag header + `data` bytes as an application-class primitive (Boolean is
  special-cased below since it has no data octets at all in this form)."
  [tag-number data]
  (let [n (count data)]
    (if (< n 5)
      (into (encode-tag-header tag-number false n) data)
      (into (into (encode-tag-header tag-number false 5) (encode-length-header n))
            data))))

(defn encode-context-tag
  "Tag header + `data` bytes as a context-class primitive."
  [tag-number data]
  (let [n (count data)]
    (if (< n 5)
      (into (encode-tag-header tag-number true n) data)
      (into (into (encode-tag-header tag-number true 5) (encode-length-header n))
            data))))

(defn encode-opening-tag [tag-number] (encode-tag-header tag-number true 6))
(defn encode-closing-tag [tag-number] (encode-tag-header tag-number true 7))

;; ── tag header (decode) ──────────────────────────────────────────────────

(defn decode-tag-header
  "Parses one tag (header only — extended length, if any, is resolved into
  `:length` here too, but the data octets themselves are not consumed).

  Returns `{:status :ok :tag-number n :context? bool :opening? bool
  :closing? bool :length n-or-nil :next offset}` where `:next` is the offset
  of the first data octet (or, for opening/closing tags, the offset right
  after the tag itself — there is no data). `:length` is nil for
  opening/closing tags and for an application-tagged Boolean, whose value is
  `:lvt-value` instead (0 or 1, read out of the LVT field, not a data byte)."
  [bs offset]
  (if-let [b0 (safe-nth bs offset)]
    (let [nibble (bit-and (unsigned-bit-shift-right b0 4) 0x0F)
          context? (bit-test b0 3)
          lvt (bit-and b0 0x07)
          after0 (inc offset)]
      (let [[tag-number after-tagnum]
            (if (= nibble 15)
              (if-let [tn (safe-nth bs after0)]
                [tn (inc after0)]
                [nil nil])
              [nibble after0])]
        (cond
          (nil? tag-number) [:error :bacnet/truncated-tag]

          (= lvt 6) (if context?
                      {:status :ok :tag-number tag-number :context? true
                       :opening? true :closing? false :length nil :next after-tagnum}
                      [:error :bacnet/opening-tag-must-be-context])

          (= lvt 7) (if context?
                      {:status :ok :tag-number tag-number :context? true
                       :opening? false :closing? true :length nil :next after-tagnum}
                      [:error :bacnet/closing-tag-must-be-context])

          (= lvt 5) ;; extended length
          (if-let [len0 (safe-nth bs after-tagnum)]
            (cond
              (< len0 254)
              {:status :ok :tag-number tag-number :context? context?
               :opening? false :closing? false :length len0 :next (inc after-tagnum)}

              (= len0 254)
              (let [b1 (safe-nth bs (+ after-tagnum 1)) b2 (safe-nth bs (+ after-tagnum 2))]
                (if (and b1 b2)
                  {:status :ok :tag-number tag-number :context? context?
                   :opening? false :closing? false
                   :length (bit-or (bit-shift-left b1 8) b2)
                   :next (+ after-tagnum 3)}
                  [:error :bacnet/truncated-tag]))

              :else ;; 255 — 4-octet length
              (let [b1 (safe-nth bs (+ after-tagnum 1)) b2 (safe-nth bs (+ after-tagnum 2))
                    b3 (safe-nth bs (+ after-tagnum 3)) b4 (safe-nth bs (+ after-tagnum 4))]
                (if (and b1 b2 b3 b4)
                  {:status :ok :tag-number tag-number :context? context?
                   :opening? false :closing? false
                   :length (bit-or (bit-shift-left b1 24) (bit-shift-left b2 16)
                                    (bit-shift-left b3 8) b4)
                   :next (+ after-tagnum 5)}
                  [:error :bacnet/truncated-tag])))
            [:error :bacnet/truncated-tag])

          :else
          {:status :ok :tag-number tag-number :context? context?
           :opening? false :closing? false :length lvt :lvt-value lvt :next after-tagnum})))
    [:error :bacnet/truncated-tag]))

;; ── Unsigned / Signed (Clause 20.2.4 / 20.2.5) ───────────────────────────
;;
;; Both are minimum-byte big-endian. Unsigned is unsigned magnitude; Signed
;; is two's complement, so the encoder must pick a byte count wide enough
;; that the sign bit of the *chosen width* matches the sign of the value —
;; 127 fits in one byte (0x7F) but -128 needs two (0xFF80), not one, because
;; one signed byte only reaches down to -128 through 0x80, and the natural
;; 'shortest unsigned magnitude' instinct gets this backwards for values
;; near a power of two.

(defn- uint->be-bytes
  "`n` (>= 0, <= 0xFFFFFFFF) as minimum-width big-endian bytes. Packing a
  value that spans more than 31 significant bits through `bit-shift-left`
  produces a JS-signed-looking intermediate (see `bacnet.object-identifier`
  for the full explanation) — safe here because extraction only ever goes
  through `bit-and`/`unsigned-bit-shift-right`, never ordinary arithmetic on
  the shifted value."
  [n]
  (cond
    (<= n 0xFF) [(u8 n)]
    (<= n 0xFFFF) [(u8 (unsigned-bit-shift-right n 8)) (u8 n)]
    (<= n 0xFFFFFF) [(u8 (unsigned-bit-shift-right n 16))
                     (u8 (unsigned-bit-shift-right n 8)) (u8 n)]
    :else [(u8 (unsigned-bit-shift-right n 24)) (u8 (unsigned-bit-shift-right n 16))
           (u8 (unsigned-bit-shift-right n 8)) (u8 n)]))

(defn encode-unsigned-value
  "Raw data bytes for an Unsigned `n` (no tag). `n` must be a non-negative
  integer that fits in 4 bytes — BACnet Unsigned is technically unbounded,
  but every use in this library (instance numbers, property array indices,
  vendor ids, APDU lengths) fits comfortably inside 32 bits, and going wider
  would need bignum-safe bit ops this library doesn't carry."
  [n]
  (cond
    (not (integer? n)) [:error :bacnet/not-an-integer]
    (neg? n) [:error :bacnet/negative-unsigned]
    (> n 0xFFFFFFFF) [:error :bacnet/unsigned-too-large]
    :else {:status :ok :bytes (uint->be-bytes n)}))

(defn decode-unsigned-value
  "`bs` (already isolated to exactly the value's `length` bytes) as an
  Unsigned. Empty input decodes to 0 per Clause 20.2.4 (Unsigned with
  length 0 is a legal, if unusual, encoding of the value zero).

  For a 4-byte value >= 0x80000000 the running total's bit 31 becomes set
  partway through the `bit-shift-left`/`bit-or` accumulation — on the JVM
  that is still an ordinary positive long, but ClojureScript's bitwise ops
  are JavaScript's, which are 32-bit *signed*: the bit pattern accumulated
  is exactly right, yet reading it back as a plain number gives a value
  2^32 too low (4000000000 comes back as -294967296). The final
  `unsigned-bit-shift-right … 0` is the standard `x >>> 0` idiom that
  reinterprets that 32-bit pattern as unsigned — a no-op on the JVM (the
  value was never negative there) and the fix on the ClojureScript side.
  Skipping this line is exactly the kind of bug that passes every JVM test
  and fails the first time this code runs in a browser."
  [bs]
  {:status :ok
   :value (unsigned-bit-shift-right
           (reduce (fn [acc b] (bit-or (bit-shift-left acc 8) (bit-and b 0xFF))) 0 bs)
           0)})

(defn encode-signed-value
  "Raw data bytes for a Signed `n` in minimum two's-complement width."
  [n]
  (cond
    (not (integer? n)) [:error :bacnet/not-an-integer]
    (< n -8388608) [:error :bacnet/signed-too-large] ;; beyond 3-byte range, not needed here
    (> n 8388607) [:error :bacnet/signed-too-large]
    (<= -128 n 127) {:status :ok :bytes [(u8 n)]}
    (<= -32768 n 32767) {:status :ok :bytes [(u8 (unsigned-bit-shift-right (bit-and n 0xFFFF) 8))
                                              (u8 n)]}
    :else {:status :ok :bytes [(u8 (unsigned-bit-shift-right (bit-and n 0xFFFFFF) 16))
                                (u8 (unsigned-bit-shift-right n 8)) (u8 n)]}))

(defn decode-signed-value
  "`bs` as a two's-complement Signed. Sign-extension is done from the
  *actual* width of `bs`, not a fixed 32 bits — a one-byte 0xFF is -1, not
  255 and not the low byte of some wider negative number."
  [bs]
  (let [n (count bs)
        magnitude (reduce (fn [acc b] (bit-or (bit-shift-left acc 8) (bit-and b 0xFF))) 0 bs)
        sign-bit (bit-shift-left 1 (dec (* n 8)))]
    {:status :ok
     :value (if (and (pos? n) (pos? (bit-and magnitude sign-bit)))
              (- magnitude (bit-shift-left 1 (* n 8)))
              magnitude)}))

;; ── Boolean (Clause 20.2.3) ──────────────────────────────────────────────

(defn encode-boolean-application
  "Application-tagged Boolean: the value lives in the LVT nibble, zero data
  octets follow. This is the one primitive whose encoded length depends on
  its own value's *type*, not its magnitude."
  [b]
  (encode-tag-header 1 false (if b 1 0)))

(defn encode-boolean-context
  "Context-tagged Boolean: an ordinary length-1 primitive whose one data
  byte is 0 or 1 — the opposite shape from the application form."
  [tag-number b]
  (encode-context-tag tag-number [(if b 1 0)]))

;; ── BACnetObjectIdentifier (Clause 20.2.14) ──────────────────────────────
;;
;; Packed into 32 bits: object-type is the top 10 bits, instance-number the
;; bottom 22. `(bit-shift-left object-type 22)` for a type near the top of
;; its 10-bit range (>= 512) sets bit 31 — the sign bit of a JS `number`
;; used as a bitwise operand. `bit-shift-left`/`bit-or` in ClojureScript
;; compile straight to JavaScript's `<<`/`|`, which treat their operands as
;; **signed** 32-bit integers, so the packed value can come back negative
;; when printed (e.g. type 1023 packs to -4194304, not 4290772992) even
;; though the underlying 32-bit *pattern* is exactly right. On the JVM the
;; same shifts happen on a 64-bit long with room to spare, so the packed
;; value prints positive there — same bits, different sign story. Neither
;; side is wrong and neither needs to be: extraction here only ever goes
;; through `bit-and`/`unsigned-bit-shift-right` (never ordinary arithmetic
;; or an ordering comparison on the packed value), and both of those read
;; the 32-bit pattern as unsigned on both platforms. Comparing the packed
;; int across platforms with `=` would be the classic mistake this avoids.

(def max-object-type 0x3FF)       ; 10 bits
(def max-instance-number 0x3FFFFF) ; 22 bits

(defn pack-object-identifier
  [object-type instance-number]
  (cond
    (not (<= 0 object-type max-object-type))
    [:error :bacnet/object-type-out-of-range]

    (not (<= 0 instance-number max-instance-number))
    [:error :bacnet/instance-number-out-of-range]

    :else
    {:status :ok
     :packed (bit-or (bit-shift-left object-type 22) instance-number)}))

(defn unpack-object-identifier
  [packed]
  {:status :ok
   :object-type (bit-and (unsigned-bit-shift-right packed 22) max-object-type)
   :instance-number (bit-and packed max-instance-number)})

(defn encode-object-identifier-value
  "Raw 4 data bytes (no tag) for `{:object-type t :instance-number i}`."
  [{:keys [object-type instance-number]}]
  (let [packed (pack-object-identifier object-type instance-number)]
    (if (= :error (first packed))
      packed
      {:status :ok
       :bytes [(u8 (unsigned-bit-shift-right (:packed packed) 24))
               (u8 (unsigned-bit-shift-right (:packed packed) 16))
               (u8 (unsigned-bit-shift-right (:packed packed) 8))
               (u8 (:packed packed))]})))

(defn decode-object-identifier-value
  "`bs` must be exactly 4 bytes — the wire encoding is always fixed-width."
  [bs]
  (if (not= 4 (count bs))
    [:error :bacnet/object-identifier-wrong-length]
    (let [packed (reduce (fn [acc b] (bit-or (bit-shift-left acc 8) (bit-and b 0xFF))) 0 bs)
          {:keys [object-type instance-number]} (unpack-object-identifier packed)]
      {:status :ok :object-type object-type :instance-number instance-number})))

;; ── whole-tag convenience: encode/decode a typed value in one call ───────

(def application-tag-numbers
  "Table 20-1, the subset this library encodes/decodes."
  {:null 0 :boolean 1 :unsigned 2 :signed 3 :enumerated 9 :object-identifier 12})

(def application-tag-number->keyword
  (into {} (map (fn [[k v]] [v k])) application-tag-numbers))

(defn encode-application-value
  "`[type value]` -> application-tagged bytes. `:enumerated` shares
  Unsigned's byte encoding (Clause 20.2.11 says so explicitly — it is not a
  coincidence to be reimplemented separately and then have the two
  encodings drift apart)."
  [type value]
  (case type
    :null (encode-tag-header 0 false 0)
    :boolean (encode-boolean-application value)
    :unsigned (let [r (encode-unsigned-value value)]
                (if (= :error (first r)) r (encode-application-tag 2 (:bytes r))))
    :signed (let [r (encode-signed-value value)]
              (if (= :error (first r)) r (encode-application-tag 3 (:bytes r))))
    :enumerated (let [r (encode-unsigned-value value)]
                  (if (= :error (first r)) r (encode-application-tag 9 (:bytes r))))
    :object-identifier (let [r (encode-object-identifier-value value)]
                          (if (= :error (first r)) r (encode-application-tag 12 (:bytes r))))
    [:error :bacnet/unsupported-value-type]))

(defn decode-application-value
  "Decodes one application-tagged primitive starting at `offset`. Returns
  `{:status :ok :type kw :value v :next offset}`."
  [bs offset]
  (let [header (decode-tag-header bs offset)]
    (if (= :error (first header))
      header
      (let [{:keys [tag-number context? opening? closing? length lvt-value next]} header]
        (cond
          context? [:error :bacnet/expected-application-tag]
          (or opening? closing?) [:error :bacnet/expected-primitive-tag]

          (= tag-number 0) {:status :ok :type :null :value nil :next next}

          (= tag-number 1) {:status :ok :type :boolean :value (= lvt-value 1) :next next}

          (contains? application-tag-number->keyword tag-number)
          (let [data (subvec (vec bs) next (+ next length))
                type (application-tag-number->keyword tag-number)]
            (case type
              :unsigned (let [r (decode-unsigned-value data)]
                          {:status :ok :type type :value (:value r) :next (+ next length)})
              :signed (let [r (decode-signed-value data)]
                        {:status :ok :type type :value (:value r) :next (+ next length)})
              :enumerated (let [r (decode-unsigned-value data)]
                            {:status :ok :type type :value (:value r) :next (+ next length)})
              :object-identifier (let [r (decode-object-identifier-value data)]
                                    (if (= :error (first r))
                                      r
                                      {:status :ok :type type
                                       :value {:object-type (:object-type r)
                                               :instance-number (:instance-number r)}
                                       :next (+ next length)}))))

          :else [:error :bacnet/unsupported-value-type])))))
