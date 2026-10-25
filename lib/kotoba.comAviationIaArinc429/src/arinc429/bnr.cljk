(ns arinc429.bnr
  "BNR — Binary, i.e. two's-complement signed numeric — encoding of the
  19-bit Data field (`arinc429.word`'s `:data`).

  Layout (this is the standard BNR convention described in public ARINC
  429 tutorials, not a per-parameter value from a real ICD — see below):
  the significant bits are LEFT-JUSTIFIED at the high end of the 19-bit
  field, immediately below SSM. A parameter's characteristics give it a
  number of Significant Bits (`sig-bits`, SB — includes the sign bit) and
  a Resolution (LSB weight, engineering units per count); any of the 19
  field bits below `sig-bits` are unused and transmitted as zero. The
  most significant of the significant bits is the SIGN bit: 0 = positive,
  1 = negative, standard two's complement.

    numeric value = (signed `sig-bits`-bit integer) * resolution

  **This namespace deliberately does not hardcode any real parameter's
  actual `sig-bits`/`resolution` pair** (e.g. the well-known 'label 320 is
  pressure altitude, N bits, R ft/count' kind of table you'll find in a
  real ICD) — those numbers come from the specific equipment's interface
  document, are legally part of the controlled standard/ICD, and inventing
  plausible-looking ones would be exactly the kind of fabricated spec
  vector this library's README warns against. Every worked example in the
  test suite uses round, clearly-invented numbers and is labelled
  accordingly. Callers with a real ICD pass their own `sig-bits`/
  `resolution`.")

(defn- round
  [x]
  #?(:clj (Math/round (double x))
     :cljs (Math/round x)))

(defn- sign-extend
  [raw sig-bits]
  (if (bit-test raw (dec sig-bits))
    (- raw (bit-shift-left 1 sig-bits))
    raw))

(defn encode
  "`value` (a number, engineering units) + `{:sig-bits N :resolution R}`
  -> `[:ok data19]`, the raw 19-bit integer ready for `arinc429.word/
  pack-word`'s `:data`.

  `[:error :arinc429/bnr-sig-bits-out-of-range n]` if `sig-bits` is not in
  1..19, or `[:error :arinc429/bnr-value-out-of-range {:value :counts
  :limit}]` if `value / resolution`, rounded, does not fit in a signed
  `sig-bits`-bit integer."
  [value {:keys [sig-bits resolution]}]
  (cond
    (not (<= 1 sig-bits 19))
    [:error :arinc429/bnr-sig-bits-out-of-range sig-bits]

    :else
    (let [counts (round (/ value resolution))
          limit (bit-shift-left 1 (dec sig-bits))]
      (if (or (< counts (- limit)) (>= counts limit))
        [:error :arinc429/bnr-value-out-of-range {:value value :counts counts :limit limit}]
        (let [raw (bit-and counts (dec (bit-shift-left 1 sig-bits)))
              fill (- 19 sig-bits)]
          [:ok (bit-shift-left raw fill)])))))

(defn decode
  "The inverse of `encode`: `data19` + the same `{:sig-bits :resolution}`
  -> `[:ok value]`."
  [data19 {:keys [sig-bits resolution]}]
  (if-not (<= 1 sig-bits 19)
    [:error :arinc429/bnr-sig-bits-out-of-range sig-bits]
    (let [fill (- 19 sig-bits)
          raw (bit-and (unsigned-bit-shift-right data19 fill)
                       (dec (bit-shift-left 1 sig-bits)))
          signed (sign-extend raw sig-bits)]
      [:ok (* signed resolution)])))
