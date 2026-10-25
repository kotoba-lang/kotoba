(ns dicom.bytes
  "Byte-level primitives for reading and writing DICOM's binary encoding.

  DICOM (PS3.5 §7.1) permits **both byte orders** — little endian is the
  default and the only one most transfer syntaxes ever use, but
  `1.2.840.10008.1.2.2` (Explicit VR Big Endian, retired in the 2016 edition
  but still legal to encounter in archived studies) exists and this library
  round-trips it. Every multi-byte read/write here takes an explicit
  `:little`/`:big` order — there is no ambient default, because a default
  is exactly the kind of thing that gets forgotten when the rare big-endian
  file finally shows up.

  Everything operates on plain vectors of ints 0..255 (`Sequential` in,
  `Sequential` out), the same convention `org-modbus`/`org-dnp3` use, so
  callers are free to feed this from a byte array, a Buffer, or a plain
  vector without a conversion shim.

  All arithmetic here is `bit-and`/`bit-or`/`bit-shift-left`/
  `unsigned-bit-shift-right` — deliberately, because JavaScript's bitwise
  operators coerce to a **signed 32-bit** ToInt32 and the JVM's `bit-or` on
  boxed longs does not. `(bit-or 0x80 (bit-shift-left 0xFF 24))` is a
  positive `0xFF000080` on the JVM and a *negative* `-16777088` under
  ClojureScript — the classic trap this module exists to avoid. The 32-bit
  length field is read here as an **unsigned long**, never combined with
  `bit-or` in a way that could produce that sign bit, precisely so the
  `0xFFFFFFFF` \"undefined length\" sentinel (PS3.5 §7.1.1) compares equal
  on both runtimes instead of becoming `-1` on one of them.")

(defn u16-le
  "Two bytes, least-significant first, as an unsigned int 0..65535."
  [b0 b1]
  (bit-or (bit-and b0 0xFF)
          (bit-shift-left (bit-and b1 0xFF) 8)))

(defn u16-be
  "Two bytes, most-significant first, as an unsigned int 0..65535."
  [b0 b1]
  (bit-or (bit-shift-left (bit-and b0 0xFF) 8)
          (bit-and b1 0xFF)))

(defn read-u16
  "Read a 2-byte unsigned int from `bs` at `offset` in byte-`order`
  (`:little` or `:big`). Returns `[value next-offset]`."
  [bs offset order]
  (let [b0 (nth bs offset) b1 (nth bs (inc offset))]
    [(if (= order :little) (u16-le b0 b1) (u16-be b0 b1))
     (+ offset 2)]))

(defn write-u16
  "2-byte encoding of unsigned `v` (0..65535) in byte-`order`."
  [v order]
  (let [lo (bit-and v 0xFF)
        hi (bit-and (unsigned-bit-shift-right v 8) 0xFF)]
    (if (= order :little) [lo hi] [hi lo])))

;; A 32-bit value is assembled as a double-precision float sum, not with
;; `bit-or`/`bit-shift-left`, on purpose: both runtimes represent integers
;; up to 2^53 exactly as doubles, and `+`/`*` on doubles never touches the
;; ToInt32 coercion that makes bit-ops on values >= 2^31 sign-dependent.
;; This is the same boundary `dnp3.objects`'s `read-u32-le` was written to
;; avoid, cited in this workspace's own `org-dnp3` README as a place two
;; agents independently got this wrong under cljs before landing on it.
(defn read-u32
  "Read a 4-byte unsigned int from `bs` at `offset` in byte-`order`.
  Returns `[value next-offset]`. `value` may exceed 2^31 (e.g. the
  `0xFFFFFFFF` undefined-length sentinel) and is returned as an exact
  non-negative integer on both runtimes."
  [bs offset order]
  (let [b (mapv #(bit-and (nth bs (+ offset %)) 0xFF) (range 4))
        b (if (= order :little) b (vec (reverse b)))
        [b0 b1 b2 b3] b]
    [(+ b0 (* b1 256) (* b2 65536) (* b3 16777216))
     (+ offset 4)]))

(defn write-u32
  "4-byte encoding of unsigned `v` (0..4294967295) in byte-`order`."
  [v order]
  (let [b0 (mod v 256)
        b1 (mod (quot v 256) 256)
        b2 (mod (quot v 65536) 256)
        b3 (mod (quot v 16777216) 256)]
    (if (= order :little) [b0 b1 b2 b3] [b3 b2 b1 b0])))

(defn slice
  "`(count n)` bytes from `bs` starting at `offset`, as a vector."
  [bs offset n]
  (vec (subvec (vec bs) offset (+ offset n))))

;; `(char->int (char-array ...))` and friends silently disagree between
;; runtimes for non-ASCII text (see `org-modbus`'s README, "A trap this
;; library's own suite fell into"). DICOM's string VRs are specified as
;; the DICOM default character repertoire (essentially US-ASCII) unless
;; a Specific Character Set element says otherwise, and this library does
;; not implement extended character sets — so bytes<->string here is
;; deliberately restricted to the one range where naive code-point
;; conversion is safe on both runtimes: 0x00-0x7F.
(defn char-code
  "Portable character -> Unicode code-point.

  **Not `int`.** `(int c)` correctly returns a code point on the JVM,
  where a Clojure character is `java.lang.Character`. In ClojureScript a
  character is just a one-character JS string, and `int` on a
  *non-numeric string* goes through JS's ToInt32 numeric coercion — which
  gives `NaN`, which `int` then reports as `0` — not the character's
  code point. `(map int \"123456789\")` therefore returns nine zeros
  under ClojureScript and the actual code points on the JVM, a trap this
  workspace's own `org-modbus` README documents having been bitten by
  three separate times in one day across three different libraries.
  `.charCodeAt` is the correct, portable primitive for this direction."
  [c]
  #?(:clj (int c)
     :cljs (.charCodeAt (str c) 0)))

(defn bytes->ascii
  "Decode `bs` as US-ASCII/DICOM-default-repertoire text. Returns
  `[:error :dicom/non-ascii-byte]` if any byte is >= 0x80 — this library
  does not implement Specific Character Set (0008,0005) extended
  repertoires, so it refuses to guess rather than mis-decode."
  [bs]
  (if (some #(>= % 0x80) bs)
    [:error :dicom/non-ascii-byte]
    [:ok (apply str (map char bs))]))

(defn ascii->bytes
  "Encode ASCII string `s` as a byte vector. `[:error
  :dicom/non-ascii-char]` if any character is outside 0x00-0x7F."
  [s]
  (let [cs (map char-code s)]
    (if (some #(>= % 0x80) cs)
      [:error :dicom/non-ascii-char]
      [:ok (vec cs)])))
