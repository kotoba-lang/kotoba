(ns dicom.vr
  "The Value Representation table — PS3.5 §6.2, Table 6.2-1.

  DICOM's data element header comes in two shapes, and which shape a given
  VR gets is **not a matter of the value's actual size** — it is a fixed
  property of the VR itself, decided once by the committee and never
  inferred. Get the classification wrong for one VR and every element
  after it in the stream is misaligned, because the decoder read the wrong
  number of length-field bytes.

  **Short form** — `VR (2 bytes) + length (2 bytes, unsigned, max 65535)`:
  AE AS AT CS DA DS DT FL FD IS LO LT PN SH SL SS ST TM UI UL US

  **Long form** — `VR (2 bytes) + reserved (2 bytes, must be 0) + length
  (4 bytes, unsigned, 0xFFFFFFFF means \"undefined\")`:
  OB OD OF OW SQ UN UT

  This is the classic place implementers get bitten: a naive encoder that
  always writes `VR + length16` works fine until the first `OB` (raw
  binary, e.g. an overlay or a private blob) or `SQ` (Sequence) shows up,
  at which point it either truncates a length > 65535 into 16 bits or
  writes two bytes of stray length where the reserved field belongs and
  desynchronises the rest of the file. There is no way to detect this by
  re-parsing your own output — it only breaks against a real decoder,
  which is why the round-trip property test here sweeps every VR in the
  table, not just the ones a first implementation happens to exercise.

  This module covers the 28 VRs enumerated in the task scope (the classic
  PS3.5 table as it stood through the file-meta-relevant editions). Newer
  editions of PS3.5 added `OL`, `OV`, `SV`, `UC`, `UR`, `UV` — all
  long-form — which are **not implemented here**; `long-form?`/`short-form?`
  return `[:error :dicom/unknown-vr]` for them rather than guessing."
  (:require [dicom.bytes :as b]))

(def short-form-vrs
  "VRs whose explicit-VR header is `VR + length16` (PS3.5 Table 6.2-1)."
  #{:AE :AS :AT :CS :DA :DS :DT :FL :FD :IS :LO :LT :PN :SH :SL :SS :ST :TM
    :UI :UL :US})

(def long-form-vrs
  "VRs whose explicit-VR header is `VR + reserved16 + length32`."
  #{:OB :OD :OF :OW :SQ :UN :UT})

(def all-vrs (into short-form-vrs long-form-vrs))

(defn short-form? [vr] (contains? short-form-vrs vr))
(defn long-form? [vr] (contains? long-form-vrs vr))

(def undefined-length
  "0xFFFFFFFF — the sentinel meaning \"length not known in advance\", legal
  only for `SQ`, `OB`/`OW` pixel data with encapsulated fragments, and the
  item/delimiter pseudo-elements that bound such sequences (PS3.5 §7.1.1)."
  0xFFFFFFFF)

(def ^:private vr->keyword
  (into {} (map (fn [k] [(name k) k]) all-vrs)))

(defn code->vr
  "Two ASCII bytes (the VR field on the wire) to a VR keyword, or
  `[:error :dicom/unknown-vr]`. `bs` is a 2-element byte vector."
  [bs]
  (let [s (apply str (map char bs))]
    (if-let [vr (get vr->keyword s)]
      [:ok vr]
      [:error :dicom/unknown-vr])))

(defn vr->code
  "VR keyword to its 2-byte ASCII wire code. Uses `dicom.bytes/char-code`,
  not `int` — see that function's docstring for why `(mapv int (name vr))`
  is a ClojureScript-only bug (every code comes back `[0 0]`, which
  `code->vr` then reports as `:dicom/unknown-vr` on every element in the
  file — the actual failure mode this had, caught only by the cljs run)."
  [vr]
  (mapv b/char-code (name vr)))

;; Whether a VR's *value* should be interpreted as a length-N array of
;; further-typed fields rather than a single scalar — used by the pixel
;; data / dataset layer to decide how a fragment's element bytes are
;; consumed, not by the header parser (the header parser only needs
;; short-form?/long-form?).
(def binary-vrs
  "VRs whose value is raw/typed binary rather than a padded text string."
  #{:AT :FL :FD :OB :OD :OF :OW :SL :SS :SQ :UL :UN :US})

(def text-vrs (into #{} (remove binary-vrs all-vrs)))
