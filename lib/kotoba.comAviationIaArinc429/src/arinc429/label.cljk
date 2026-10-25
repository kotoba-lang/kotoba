(ns arinc429.label
  "The ARINC 429 Label field (word bits 1-8) and its octal/wire reversal.

  **Provenance note (read this before trusting a number here): the exact
  wording of AEEC/ARINC 429 itself is a paid SAE ITC document this
  implementation has not seen.** What follows is reconstructed from
  publicly available secondary sources — general-aviation ARINC 429
  tutorials and application notes published by test-equipment vendors
  (e.g. the kind of \"ARINC 429 Tutorial\" PDFs distributed by Excalibur
  Systems, AIM-Online, Condor Engineering/GE and similar avionics bus
  analyser vendors) that describe the label-reversal behaviour below as a
  well-known, oft-repeated gotcha. It is NOT a citation of the standard's
  own text, and it is the single least-confident value in this whole
  library — see the README.

  Every ARINC 429 word is transmitted least-significant-bit first: bit 1
  goes out on the wire first, bit 32 (parity) last. That is uniform across
  the whole word, label included — the label's 8 bits sit in word bits
  1-8, i.e. the low byte, exactly like SDI/SSM sit in their own byte-aligned
  positions.

  The reversal is between THAT wire byte and how the label is CONVENTIONALLY
  WRITTEN DOWN as a 3-digit octal number (e.g. \"203\", \"270\"). The octal
  digits are formed by treating word bit 8 as the most-significant bit of
  the printed number and word bit 1 as its least-significant bit — which is
  the OPPOSITE of the LSB-first order every other multi-bit field in the
  word uses (SDI, Data and SSM are all read with the *lowest*-numbered bit
  of the field as its least-significant bit). Concretely: octal label 203
  is binary `10000011` when you write it down the normal way (MSB first,
  as you would any octal-to-binary conversion) — but the bits that actually
  go out on the wire, in transmission order (bit 1 first), are
  `1 1 0 0 0 0 0 1`, i.e. that same byte MIRRORED. `reverse-byte` is
  exactly this mirror, and because it is its own inverse, the same function
  converts in both directions.

  Get this backwards (treat the wire byte as the printed octal number
  directly, or vice versa) and you get a *different, still-plausible-looking*
  3-digit octal label — never garbage, never an error, just the wrong
  parameter. That is what makes it the classic bug: nothing in the frame
  detects it."
  (:require [arinc429.bits :as bits]))

(defn octal-label->wire-byte
  "Octal label, as a plain integer 0..255 (write `0203` in Clojure source,
  or parse the printed 3-digit octal string with `octal-str->label`) ->
  the byte that occupies word bits 1-8 in transmission order.

  `[:ok byte]` or `[:error :arinc429/label-out-of-range n]`."
  [octal-label]
  (if (<= 0 octal-label 0xFF)
    [:ok (bits/reverse-byte octal-label)]
    [:error :arinc429/label-out-of-range octal-label]))

(defn wire-byte->octal-label
  "The inverse of `octal-label->wire-byte`: the byte occupying word bits
  1-8, in transmission order -> the octal label as a plain integer 0..255.

  `reverse-byte` is an involution, so this is literally the same
  computation as the encode direction — that symmetry is itself the
  strongest evidence that the convention is self-consistent, independent
  of whether the underlying convention this library assumed is the one
  the paid standard actually specifies."
  [wire-byte]
  (if (<= 0 wire-byte 0xFF)
    [:ok (bits/reverse-byte wire-byte)]
    [:error :arinc429/label-out-of-range wire-byte]))

(defn octal-str->label
  "Parse a printed octal label like \"203\" or \"270\" into the plain
  integer 0..255 this namespace's other functions take. `[:ok n]` or
  `[:error :arinc429/not-octal s]`."
  [s]
  #?(:clj
     (try [:ok (Integer/parseInt s 8)]
          (catch NumberFormatException _ [:error :arinc429/not-octal s]))
     :cljs
     (if (re-matches #"[0-7]+" s)
       [:ok (js/parseInt s 8)]
       [:error :arinc429/not-octal s])))

(defn label->octal-str
  "The plain integer 0..255 -> its printed 3-digit octal form, e.g. 131 ->
  \"203\"."
  [n]
  #?(:clj (format "%03o" n)
     :cljs (let [s (.toString n 8)]
             (str (apply str (repeat (max 0 (- 3 (count s))) "0")) s))))
