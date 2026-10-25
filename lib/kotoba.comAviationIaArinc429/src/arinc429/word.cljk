(ns arinc429.word
  "The full 32-bit ARINC 429 word: Label (bits 1-8) + SDI (9-10) + Data
  (11-29, 19 bits) + SSM (30-31) + odd Parity (32).

  Bit numbering follows the convention used throughout this library: ARINC
  bit N is stored at integer bit (N-1), so ARINC bit 1 (first bit
  transmitted) is the least-significant bit of the integer word, and ARINC
  bit 32 (parity, last bit transmitted) is the most-significant bit — the
  word as a whole is read the same LSB-first direction the wire sends it
  in. This is uniform across the word; only the printed octal LABEL breaks
  that uniformity, and that reversal is confined to `arinc429.label`
  rather than leaking into this namespace's bit-position arithmetic.

  `pack-word`/`unpack-word` do not know or care whether the Data field is
  BNR, BCD or Discrete — that is `arinc429.bnr`/`arinc429.bcd`/
  `arinc429.ssm`'s job, layered on top of the raw 19-bit integer this
  namespace hands back. Keeping the layers separate is what lets the same
  parity/framing code serve all three data types."
  (:require [arinc429.bits :as bits]))

(def data-bits 19)
(def data-mask (dec (bit-shift-left 1 data-bits)))

(def label-shift 0)
(def sdi-shift 8)
(def data-shift 10)
(def ssm-shift 29)
(def parity-shift 31)

(defn- valid-fields
  [{:keys [label sdi data ssm]}]
  (cond
    (not (<= 0 label 0xFF)) [:error :arinc429/label-out-of-range label]
    (not (<= 0 sdi 3)) [:error :arinc429/sdi-out-of-range sdi]
    (not (<= 0 data data-mask)) [:error :arinc429/data-out-of-range data]
    (not (<= 0 ssm 3)) [:error :arinc429/ssm-out-of-range ssm]
    :else nil))

(defn pack-word
  "`{:label octal-label-int :sdi 0-3 :data 0-0x7FFFF :ssm 0-3}` -> `[:ok
  word]`, a canonical (non-negative, `arinc429.bits/u32`-ed) 32-bit
  integer with the odd-parity bit already computed and set. `:label` is
  the plain integer 0..255 form (see `arinc429.label`), not the octal
  wire byte — this function does the label reversal for you.

  `[:error kw offending-value]` if any field is out of range; the label
  reversal itself cannot fail once the range check passes (`reverse-byte`
  is total over 0..255)."
  [{:keys [label sdi data ssm] :as fields}]
  (if-let [err (valid-fields fields)]
    err
    (let [wire-label (bits/reverse-byte label)
          unparitied (bits/u32
                      (bit-or (bit-shift-left wire-label label-shift)
                              (bit-shift-left sdi sdi-shift)
                              (bit-shift-left data data-shift)
                              (bit-shift-left ssm ssm-shift)))
          ones (bits/popcount32 unparitied)
          parity-bit (bit-and 1 (inc ones))]
      [:ok (bits/u32 (bit-or unparitied (bit-shift-left parity-bit parity-shift)))])))

(defn parity-ok?
  "True when `word`'s bit 32 makes the total number of 1-bits across all
  32 bits odd — the defining property of odd parity. Checked by counting
  the WHOLE word (parity bit included), which is equivalent to, and
  simpler than, computing the expected bit and comparing."
  [word]
  (odd? (bits/popcount32 (bits/u32 word))))

(defn unpack-word
  "Canonical 32-bit `word` -> `[:ok {:label :sdi :data :ssm}]`, where
  `:label` is the plain 0..255 integer (already un-reversed) and `:data`
  is the raw, uninterpreted 19-bit integer.

  `[:error :arinc429/parity-mismatch word]` if the odd-parity check
  fails — this is the one negative case this namespace itself detects;
  field-level range errors cannot occur on decode because every field
  extraction is masked to its exact bit width."
  [word]
  (let [w (bits/u32 word)]
    (if-not (parity-ok? w)
      [:error :arinc429/parity-mismatch w]
      [:ok {:label (bits/reverse-byte (bits/field w label-shift 8))
            :sdi (bits/field w sdi-shift 2)
            :data (bits/field w data-shift data-bits)
            :ssm (bits/field w ssm-shift 2)}])))
