(ns iso-8583.bcd
  "Packed decimal (BCD) and the ISO/IEC 7813 track-2 nibble encoding ISO
  8583's `b`/`n`/`z` content types use on the wire, alongside the plain
  ASCII digit form implementations that are not bit-squeezed also use.
  Two decimal digits pack into one byte, most significant nibble first --
  `bit-shift-left`/`bit-and`/`bit-or`/`unsigned-bit-shift-right`, not a
  string of two `subs` calls turned into a number, because the point of
  BCD is that it never goes through a string representation on the wire.

  A packed byte cannot say by itself whether it holds one significant
  digit or two -- `05` and `50` differ only in which nibble is the pad --
  so every unpack function here takes the exact digit count as a
  parameter rather than trying to infer it. That count always comes from
  the field's length descriptor (a fixed length, or a decoded LL/LLL
  prefix), never guessed from the byte count.

  **Padding convention (a real customisation point):** an odd digit count
  is packed with a leading zero nibble -- `\"5\"` becomes byte `0x05`, not
  `0x50`. This is the convention this codec commits to end to end
  (`pack-digits`/`unpack-digits` are exact inverses of each other under
  it); other implementations pad the *trailing* nibble instead. Because
  BCD carries no self-describing length, an acquirer's actual choice here
  is not observable from the bytes alone and must be confirmed against
  their interface specification -- this is exactly why `iso-8583.fields`
  makes the field table, and not just this convention, a parameter."
  (:require [iso-8583.charcode :as cc]))

(def ^:private code-0 (cc/char-code \0))

(defn valid-digits?
  [s]
  (and (string? s) (pos? (count s))
       (every? #(<= code-0 (cc/char-code %) (+ code-0 9)) s)))

(defn pack-digits
  "Pack a digit string into BCD bytes, most significant nibble first. An
  odd-length input is padded with a leading zero nibble (see namespace
  docstring). Returns `nil` if `s` is not all decimal digits."
  [s]
  (when (valid-digits? s)
    (let [padded (if (odd? (count s)) (str "0" s) s)]
      (vec (map (fn [[hi lo]]
                  (bit-or (bit-shift-left (- (cc/char-code hi) code-0) 4)
                          (bit-and (- (cc/char-code lo) code-0) 0xF)))
                (partition 2 padded))))))

(defn unpack-digits
  "Inverse of `pack-digits`: `n` decimal digits out of `bs` (a byte
  sequence of `(quot (inc n) 2)` bytes). `n` must be supplied by the
  caller from the field's length descriptor -- see namespace docstring."
  [bs n]
  (let [all (apply str
                    (mapcat (fn [b]
                              [(char (+ code-0 (bit-and (unsigned-bit-shift-right b 4) 0xF)))
                               (char (+ code-0 (bit-and b 0xF)))])
                            bs))]
    (subs all (- (count all) n))))

(defn byte-count
  "Bytes needed to BCD-pack `n` decimal digits (or track-2 characters)."
  [n]
  (quot (inc n) 2))

;; ---------------------------------------------------------------------
;; ISO/IEC 7813 track 2, packed: digits map to their own nibble value,
;; the field separator `=` maps to nibble 0xD, and an odd-length value is
;; padded with a trailing 0xF ("fill") nibble -- the convention documented
;; across POS/track-reader interface specs for packed track-2 data.
;; Constructed from that widely used convention, not transcribed from
;; ISO 8583's own spec text (track 2 formatting belongs to ISO/IEC 7813,
;; not to ISO 8583 itself).

(def ^:private track2-alphabet "0123456789=")

(defn valid-track2?
  [s]
  (and (string? s) (pos? (count s))
       (every? #(not= -1 #?(:clj (.indexOf ^String track2-alphabet (str %))
                             :cljs (.indexOf track2-alphabet %)))
               s)))

(defn- track2-char->nibble
  [c]
  (if (= c \=) 0xD (- (cc/char-code c) code-0)))

(defn- track2-nibble->char
  [n]
  (if (= n 0xD) \= (char (+ code-0 n))))

(defn pack-track2
  "Pack track-2 characters (`0`-`9` and `=`) into nibbles, trailing-padded
  with `0xF` if the count is odd. Returns `nil` on an invalid character."
  [s]
  (when (valid-track2? s)
    (let [nibbles (mapv track2-char->nibble s)
          nibbles (if (odd? (count nibbles)) (conj nibbles 0xF) nibbles)]
      (vec (map (fn [[hi lo]] (bit-or (bit-shift-left hi 4) (bit-and lo 0xF)))
                 (partition 2 nibbles))))))

(defn unpack-track2
  "Inverse of `pack-track2`. `n` is the exact character count (from the
  field's length descriptor)."
  [bs n]
  (let [nibbles (mapcat (fn [b] [(bit-and (unsigned-bit-shift-right b 4) 0xF)
                                  (bit-and b 0xF)])
                         bs)]
    (apply str (map track2-nibble->char (take n nibbles)))))
