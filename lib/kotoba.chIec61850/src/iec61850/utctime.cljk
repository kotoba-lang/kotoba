(ns iec61850.utctime
  "The IEC 61850-7-2 `UtcTime` type: an 8-octet **binary** timestamp, not the
  ASN.1 universal `UTCTime` string (tag 23, `YYMMDDHHMMSSZ`) that
  `asn1.core`'s `utc-time` constructor builds. GOOSE's `t` field is
  `[4] IMPLICIT UtcTime` where `UtcTime` is this binary type, so on the wire
  it is 8 raw content octets under a context tag — there is no nested BER
  structure to decode, which is why this namespace does not touch
  `asn1.core` at all.

  Layout (IEC 61850-7-2 §6.2.2, as reproduced in widely-deployed open
  implementations — libiec61850's `hal_time.c` / `Timestamp` type and
  Wireshark's public `packet-goose.c` dissector — since the IEC text itself
  is paywalled and not quoted here from memory):

  ```
  octet 0-3   SecondSinceEpoch     uint32 big-endian, seconds since 1970-01-01T00:00:00Z
  octet 4-6   FractionOfSecond     uint24 big-endian, fixed-point: value / 2^24 seconds
  octet 7     TimeQuality
                bit 7 (0x80)  LeapSecondsKnown
                bit 6 (0x40)  ClockFailure
                bit 5 (0x20)  ClockNotSynchronized
                bits 4-0      TimeAccuracy: number of significant bits in
                              FractionOfSecond (0-24), 0x1F = unspecified
  ```

  The classic bug this buys a test against: reading FractionOfSecond as a
  plain fraction (`raw/1000000`, treating it as microseconds) instead of
  `raw / 2^24`. Both give a plausible-looking sub-second value for small
  inputs and only disagree once you check a published boundary — which is
  exactly why the round-trip test below is not enough on its own and the
  suite also asserts a numeric value at a known fraction.")

(def ^:private two-pow-24 (bit-shift-left 1 24))

(defn- u32be [n]
  [(bit-and (unsigned-bit-shift-right n 24) 0xFF)
   (bit-and (unsigned-bit-shift-right n 16) 0xFF)
   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
   (bit-and n 0xFF)])

(defn- rd-u32be [bs off]
  (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 24)
          (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 16)
          (bit-shift-left (bit-and (nth bs (+ off 2)) 0xFF) 8)
          (bit-and (nth bs (+ off 3)) 0xFF)))

(defn- u24be [n]
  [(bit-and (unsigned-bit-shift-right n 16) 0xFF)
   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
   (bit-and n 0xFF)])

(defn- rd-u24be [bs off]
  (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 16)
          (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 8)
          (bit-and (nth bs (+ off 2)) 0xFF)))

(defn- round-half-up
  "`Math/round`, coerced to `double` first so `:clj`'s reflective call has an
  unambiguous overload to pick (an `int`/`long`/ratio argument — which `0`
  and every other non-float literal in this namespace's test suite is —
  otherwise fails reflection with \"no matching method\" rather than
  quietly picking the wrong one, which is the safer of the two failure
  modes but still needs heading off)."
  [x]
  #?(:clj (Math/round (double x)) :cljs (js/Math.round x)))

(defn seconds+fraction->fraction-octets
  "The fixed-point `FractionOfSecond` for a fraction `f` in `[0,1)`, computed
  as `round(f * 2^24)` and clamped to the 24-bit range. `2^24` and not
  `10^6` — this is a binary fixed-point fraction, not microseconds, even
  though a microsecond count in the low millions happens to look similar in
  magnitude for small values."
  [f]
  (-> (round-half-up (* f two-pow-24))
      (max 0)
      (min 0xFFFFFF)))

(defn fraction-octets->seconds
  "The reverse of `seconds+fraction->fraction-octets`: the 24-bit fixed-point
  value as a fraction of a second in `[0,1)`."
  [raw]
  (/ (double raw) two-pow-24))

(defn encode
  "`{:seconds <uint32> :fraction <0..1 double, or already an int 0..0xFFFFFF
  via :fraction-raw> :leap-seconds-known? :clock-failure?
  :clock-not-synchronized? :time-accuracy <0..31>}` → 8 octets.

  `:fraction-raw` (an already-quantized 24-bit int) wins over `:fraction` (a
  0..1 double) when both are given, so a decoded timestamp can be
  re-encoded without a lossy fraction->double->fraction round trip."
  [{:keys [seconds fraction fraction-raw
           leap-seconds-known? clock-failure? clock-not-synchronized?
           time-accuracy]
    :or {fraction 0 time-accuracy 0}}]
  (let [frac-raw (or fraction-raw (seconds+fraction->fraction-octets fraction))
        quality (bit-or (if leap-seconds-known? 0x80 0)
                         (if clock-failure? 0x40 0)
                         (if clock-not-synchronized? 0x20 0)
                         (bit-and time-accuracy 0x1F))]
    (into (u32be seconds) (conj (u24be frac-raw) quality))))

(defn decode
  "8 octets → the map `encode` takes (plus `:fraction-raw`), or
  `[:error :iec61850.utctime/wrong-length {:length n}]` — a UtcTime is
  fixed-width, so a truncated or padded field is not a different value, it
  is not a UtcTime at all."
  [bytes]
  (let [bs (vec bytes)]
    (if (not= 8 (count bs))
      [:error :iec61850.utctime/wrong-length {:length (count bs)}]
      (let [seconds (rd-u32be bs 0)
            frac-raw (rd-u24be bs 4)
            q (nth bs 7)]
        [:ok {:seconds seconds
              :fraction-raw frac-raw
              :fraction (fraction-octets->seconds frac-raw)
              :leap-seconds-known? (pos? (bit-and q 0x80))
              :clock-failure? (pos? (bit-and q 0x40))
              :clock-not-synchronized? (pos? (bit-and q 0x20))
              :time-accuracy (bit-and q 0x1F)}]))))
