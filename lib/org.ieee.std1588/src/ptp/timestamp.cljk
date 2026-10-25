(ns ptp.timestamp
  "The two time-valued wire formats PTP uses: the 80-bit Timestamp (clause
  5.3.3) and the 64-bit correctionField (clause 5.3.7 / 13.3.2.6, a
  TimeInterval-shaped \"scaled nanoseconds\" value).

  Both are wider than a JavaScript bitwise operator can touch in one piece.
  `bit-and`/`bit-or`/`bit-shift-left`/`unsigned-bit-shift-right` all convert
  their operand to a *signed 32-bit* integer first under ClojureScript —
  `(bit-shift-left 0xFF 24)` is a negative number there, and a *positive*
  4278190080 on the JVM, where these operators work on 64-bit longs
  instead. `org-modbus`'s README documents the same class of bug catching a
  UTF-8 encoder (`(map int \"…\")` returning code points on the JVM and
  zeros under cljs); a 48-bit seconds field or a 64-bit correctionField
  shifted as one number the way a 16-bit field can be would be this
  library's version of it.

  The fix used throughout this namespace: extract or place *one byte at a
  time* with real `bit-and` (always exact — a byte value never leaves the
  8-bit range that operator is exact for), and cross a byte boundary wider
  than 32 bits with plain multiplication/`quot`/`rem` instead of a wide
  shift. Every value this library actually carries — timestamps’ seconds
  field (48 bits), correctionField magnitudes of at most a few seconds of
  scaled nanoseconds — stays inside JavaScript's 2^53 exact-integer range,
  so the arithmetic is exact on both runtimes. It would not be for a
  correctionField near its full ±2^63 range or a seconds value near 2^48;
  this library does not attempt those and says so below.")

;; ── byte-at-a-time big/little helpers ───────────────────────────────────────

(defn- pow256 [n] (reduce * 1 (repeat n 256)))

(defn- write-uint-be
  "Non-negative `v` as `width` big-endian bytes. Each byte comes off with
  `bit-and 0xFF`; crossing a byte boundary uses `quot` by a power of 256,
  not a shift, because `v` can be wider than the 32 bits a shift is exact
  for (see namespace docstring). `v` must be an exact integer < 2^53."
  [v width]
  (loop [i (dec width) acc []]
    (if (neg? i)
      acc
      (recur (dec i) (conj acc (bit-and (quot v (pow256 i)) 0xFF))))))

(defn- read-uint-be
  "`width` big-endian bytes at `bs[off..]` -> a non-negative integer. Each
  byte is masked with `bit-and 0xFF`; combined across the boundary with
  multiplication, the same asymmetry `org-modbus/modbus.pdu`'s `rd16`
  helper uses for its 16-bit fields."
  [bs off width]
  (loop [i 0 acc 0]
    (if (= i width)
      acc
      (recur (inc i) (+ (* acc 256) (bit-and (nth bs (+ off i)) 0xFF))))))

(defn- negate-be-bytes
  "Two's-complement negation of a big-endian byte vector: invert every
  byte, then add 1 with carry propagating from the *last* (least
  significant) byte — the standard NOT-then-increment construction, done
  byte-wise so it never needs a 64-bit-wide bitwise operator."
  [bs]
  (let [inverted (mapv #(bit-and (bit-not %) 0xFF) bs)]
    (loop [i (dec (count inverted)) carry 1 out inverted]
      (if (or (neg? i) (zero? carry))
        out
        (let [sum (+ (nth out i) carry)]
          (recur (dec i) (if (> sum 0xFF) 1 0) (assoc out i (bit-and sum 0xFF))))))))

;; ── Timestamp, clause 5.3.3 ──────────────────────────────────────────────────
;; 48-bit seconds (secondsField, UInteger48) + 32-bit nanoseconds
;; (nanosecondsField, UInteger32) = 10 bytes. The epoch is 1970-01-01 00:00
;; TAI (clause 7.2.3) — TAI, not UTC, and this library does not convert
;; between the two; see README, "what this is not".

(def max-seconds "2^48 - 1, the width of secondsField." 0xFFFFFFFFFFFF)
(def max-nanoseconds "2^32 - 1, the width of nanosecondsField." 0xFFFFFFFF)

(defn encode-timestamp
  "{:seconds s :nanoseconds n} -> `[:ok bytes]`, 10 of them."
  [{:keys [seconds nanoseconds]}]
  (cond
    (not (<= 0 seconds max-seconds)) [:error :ptp/seconds-out-of-range seconds]
    (not (<= 0 nanoseconds max-nanoseconds)) [:error :ptp/nanoseconds-out-of-range nanoseconds]
    :else [:ok (into (write-uint-be seconds 6) (write-uint-be nanoseconds 4))]))

(defn decode-timestamp
  "10 bytes -> `[:ok {:seconds s :nanoseconds n}]`."
  [bs]
  (let [bs (vec bs)]
    (if (not= 10 (count bs))
      [:error :ptp/bad-timestamp-length (count bs)]
      [:ok {:seconds (read-uint-be bs 0 6) :nanoseconds (read-uint-be bs 6 4)}])))

;; ── correctionField, clause 13.3.2.6 ─────────────────────────────────────────
;; An Integer64 whose value is nanoseconds multiplied by 2^16 ("scaled
;; nanoseconds") — the low 16 bits are sub-nanosecond precision, which most
;; stacks (and this library, on encode) fill with zero. Getting the ×2^16
;; wrong by using the raw nanosecond count as the wire value produces a
;; correctionField that is off by exactly a factor of 65536, which for a
;; typical few-hundred-nanosecond residence time reads back as either
;; "basically zero" or "several minutes" depending on which side got it
;; wrong — both plausible-looking and both silently corrupting every
;; downstream offset calculation in `ptp.offset`.

(defn encode-correction
  "Whole nanoseconds (may be negative) -> `[:ok bytes]`, 8 of them, the
  Integer64 scaled-nanoseconds value ns*2^16. Fractional (sub-nanosecond)
  correction is not accepted here — only whole-nanosecond callers, which is
  every caller in this workspace. `ns` must satisfy
  `abs(ns) < 2^53 / 65536` (~137e9 ns, ~137 seconds) for the ×2^16
  multiplication to stay inside JavaScript's exact-integer range; nothing
  in real PTP operation approaches that."
  [ns]
  (cond
    (not (integer? ns)) [:error :ptp/correction-must-be-integer-nanoseconds ns]
    (not (< (if (neg? ns) (- ns) ns) 2097152000000)) ; abs(ns), well within 2^53/65536
    [:error :ptp/correction-out-of-range ns]
    :else
    (let [scaled (* ns 65536)]
      [:ok (if (neg? scaled)
             (negate-be-bytes (write-uint-be (- scaled) 8))
             (write-uint-be scaled 8))])))

(defn decode-correction
  "8 bytes -> `[:ok {:nanoseconds n-or-nil :scaled-nanoseconds n}]`.
  `:scaled-nanoseconds` is the raw Integer64 value (units of 1/65536 ns) and
  always present. `:nanoseconds` is `scaled / 65536` when that division is
  exact — true for anything this library's own `encode-correction`
  produced — and `nil` when the wire value carries a sub-nanosecond
  fraction this library does not represent, rather than silently
  truncating it away."
  [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :ptp/bad-correction-length (count bs)]
      (let [negative? (not (zero? (bit-and (nth bs 0) 0x80)))
            magnitude-bytes (if negative? (negate-be-bytes bs) bs)
            magnitude (read-uint-be magnitude-bytes 0 8)
            scaled (if negative? (- magnitude) magnitude)]
        [:ok {:nanoseconds (when (zero? (rem scaled 65536)) (quot scaled 65536))
              :scaled-nanoseconds scaled}]))))
