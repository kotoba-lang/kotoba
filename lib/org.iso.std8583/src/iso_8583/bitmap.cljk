(ns iso-8583.bitmap
  "The ISO 8583 bitmap: one bit per field, bit 1 the leftmost (most
  significant) bit of the first byte, bit 64 the rightmost bit of the
  eighth. This module works in *relative* bit positions 1..64 within a
  single 8-byte bitmap level; `iso-8583.codec` maps those onto absolute
  field numbers (primary bit N <-> field N; secondary bit N <-> field
  64+N; tertiary bit N <-> field 128+N).

  Bit 1 of a bitmap is not an ordinary data field: it announces whether
  the *next* bitmap level is present -- primary bit 1 announces the
  secondary bitmap (fields 65-128), secondary bit 1 announces the
  tertiary bitmap (fields 129-192). That chained-indicator shape is this
  codec's committed convention for tertiary-bitmap support; ISO 8583
  itself only standardises the primary/secondary pair, and how (or
  whether) a given network extends that to a third level is a
  network-specific customisation, same as the field table.

  `bit-shift-left`/`bit-and`/`bit-or`/`unsigned-bit-shift-right` do the
  actual bit packing; there is no shortcut through decimal arithmetic
  that stays correct once bit 8 (the sign bit position in a signed byte)
  is involved."
  (:require [kotoba.lang.text :as str]))

(defn relative-fields->bytes
  "`field-nums`: a set of ints in 1..64 (bit positions within one bitmap
  level). Returns 8 bytes, MSB-first within each byte."
  [field-nums]
  (vec (for [byte-idx (range 8)]
         (reduce (fn [b bit-idx]
                   (let [bit-num (+ (* byte-idx 8) bit-idx 1)]
                     (if (contains? field-nums bit-num)
                       (bit-or b (bit-shift-left 1 (- 7 bit-idx)))
                       b)))
                 0
                 (range 8)))))

(defn bytes->relative-fields
  "Inverse of `relative-fields->bytes`. `bs` must be exactly 8 bytes."
  [bs]
  (set (for [byte-idx (range 8)
             bit-idx (range 8)
             :when (not (zero? (bit-and (nth bs byte-idx)
                                         (bit-shift-left 1 (- 7 bit-idx)))))]
         (+ (* byte-idx 8) bit-idx 1))))

;; ---------------------------------------------------------------------
;; ASCII-hex bitmap representation (16 upper-case hex characters per
;; 8-byte level) -- the form text-oriented ISO 8583 carriers (and this
;; codec's `:bitmap-encoding :hex`) use instead of raw binary.

(def ^:private hex-digits "0123456789ABCDEF")

(defn bytes->hex
  [bs]
  (apply str (mapcat (fn [b]
                        [(nth hex-digits (bit-and (unsigned-bit-shift-right b 4) 0xF))
                         (nth hex-digits (bit-and b 0xF))])
                      bs)))

(defn- hex-char->nibble
  "-1 for a character that is not a hex digit, upper or lower case."
  [c]
  (let [up (first (str/upper (str c)))]
    #?(:clj (.indexOf ^String hex-digits (str up))
       :cljs (.indexOf hex-digits up))))

(defn hex->bytes
  "Inverse of `bytes->hex`. `nil` if `s` is not 16 valid hex characters."
  [s]
  (when (and (string? s) (= 16 (count s)))
    (let [nibbles (map hex-char->nibble s)]
      (if (some neg? nibbles)
        nil
        (vec (map (fn [[hi lo]] (bit-or (bit-shift-left hi 4) lo))
                   (partition 2 nibbles)))))))
