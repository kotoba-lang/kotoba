(ns tar.bytes
  "Byte-level helpers for the tar header: octal (and GNU base-256) numeric
   fields, NUL-terminated strings, UTF-8 ⇄ string.

   Deliberately a self-contained copy rather than a dependency — this repo has
   zero deps, the same reason `org-pkware-zip` carries its own `zip.bytes` and
   the GIF/TIFF codecs carry their own LZW (ADR-2607082500's layering
   principle)."
  (:refer-clojure :exclude [bytes]))

(defn u8 [bv o] (nth bv o))

(defn slice [bv from to] (subvec (vec bv) from to))

(defn- trim-field
  "tar pads its fields with NUL and/or space; either may terminate a value."
  [bs]
  (vec (take-while #(and (not= % 0) (not= % 0x20)) (drop-while #(= % 0x20) bs))))

(declare utf8->str)

(defn read-str
  "A NUL-terminated (or field-length-limited) field, decoded as UTF-8.

   POSIX says these fields are bytes and leaves the character set to the writer;
   in practice everything since the 1990s writes UTF-8, and decoding as Latin-1
   turns a Japanese filename into mojibake that round-trips *almost* correctly —
   the worst kind of bug, because the bytes survive and only the name is wrong."
  [bv off len]
  (utf8->str (take-while #(not= % 0) (subvec (vec bv) off (+ off len)))))

(defn read-numeric
  "A tar numeric field: octal ASCII by default, or GNU base-256 when the high
   bit of the first byte is set (how sizes above 8 GiB and negative timestamps
   are carried).

   An empty field is 0 — tar leaves size blank for entries that have no data."
  [bv off len]
  (let [bs (subvec (vec bv) off (+ off len))
        b0 (first bs)]
    (if (and b0 (pos? (bit-and b0 0x80)))
      ;; Base-256: a big-endian two's-complement integer whose sign lives in bit
      ;; 0x40 of the first byte (the 0x80 bit is only the escape marker). Built
      ;; with multiplication rather than shifts so it stays exact past 32 bits on
      ;; a JavaScript runtime.
      (loop [i 1 acc (+ (* (if (pos? (bit-and b0 0x40)) -1 0) 64)
                        (bit-and b0 0x3f))]
        (if (>= i (count bs))
          acc
          (recur (inc i) (+ (* acc 256) (nth bs i)))))
      (let [digits (trim-field bs)]
        (if (empty? digits)
          0
          (loop [i 0 acc 0]
            (if (>= i (count digits))
              acc
              (let [d (- (nth digits i) 48)]
                (when (or (neg? d) (> d 7))
                  (throw (ex-info "tar: field is not octal"
                                  {:reason :bad-numeric-field :offset off})))
                (recur (inc i) (+ (* acc 8) d))))))))))

(defn octal-field
  "Format `value` as `(dec width)` octal digits followed by NUL — the encoding
   every tar reader accepts."
  [value width]
  (let [digits (dec width)
        ;; Vectors, not lists: SCI (nbb) does not evaluate an empty-list literal
        ;; or a quoted list the way the JVM does, and this ran fine on the JVM
        ;; while failing on every ClojureScript call.
        s      (loop [v value out []]
                 (if (zero? v)
                   (if (seq out) out [48])
                   (recur (quot v 8) (into [(+ 48 (mod v 8))] out))))]
    (when (> (count s) digits)
      (throw (ex-info "tar: value does not fit its octal field"
                      {:reason :field-overflow :value value :width width})))
    (into (vec (repeat (- digits (count s)) 48)) (conj s 0))))

(defn- char-code [c]
  #?(:clj (int c) :cljs (.charCodeAt c 0)))

(defn str->utf8 [s]
  (let [v (vec (seq s)) n (count v)]
    (loop [i 0 out []]
      (if (>= i n)
        out
        (let [c (char-code (nth v i))]
          (cond
            (< c 0x80) (recur (inc i) (conj out c))
            (< c 0x800) (recur (inc i) (conj out (bit-or 0xc0 (unsigned-bit-shift-right c 6))
                                            (bit-or 0x80 (bit-and c 0x3f))))
            (and (<= 0xd800 c 0xdbff) (< (inc i) n)
                 (<= 0xdc00 (char-code (nth v (inc i))) 0xdfff))
            (let [lo (char-code (nth v (inc i)))
                  cp (+ 0x10000 (bit-shift-left (- c 0xd800) 10) (- lo 0xdc00))]
              (recur (+ i 2) (conj out
                                   (bit-or 0xf0 (unsigned-bit-shift-right cp 18))
                                   (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 12) 0x3f))
                                   (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 6) 0x3f))
                                   (bit-or 0x80 (bit-and cp 0x3f)))))
            :else (recur (inc i) (conj out (bit-or 0xe0 (unsigned-bit-shift-right c 12))
                                       (bit-or 0x80 (bit-and (unsigned-bit-shift-right c 6) 0x3f))
                                       (bit-or 0x80 (bit-and c 0x3f))))))))))

(defn utf8->str [bs]
  (let [v (vec bs) n (count v)]
    (loop [i 0 out ""]
      (if (>= i n)
        out
        (let [b (nth v i)]
          (cond
            (< b 0x80) (recur (inc i) (str out (char b)))

            (and (= 0xc0 (bit-and b 0xe0)) (< (+ i 1) n))
            (recur (+ i 2) (str out (char (bit-or (bit-shift-left (bit-and b 0x1f) 6)
                                                  (bit-and (nth v (+ i 1)) 0x3f)))))

            (and (= 0xe0 (bit-and b 0xf0)) (< (+ i 2) n))
            (recur (+ i 3) (str out (char (bit-or (bit-shift-left (bit-and b 0x0f) 12)
                                                  (bit-shift-left (bit-and (nth v (+ i 1)) 0x3f) 6)
                                                  (bit-and (nth v (+ i 2)) 0x3f)))))

            (and (= 0xf0 (bit-and b 0xf8)) (< (+ i 3) n))
            (let [cp  (bit-or (bit-shift-left (bit-and b 0x07) 18)
                              (bit-shift-left (bit-and (nth v (+ i 1)) 0x3f) 12)
                              (bit-shift-left (bit-and (nth v (+ i 2)) 0x3f) 6)
                              (bit-and (nth v (+ i 3)) 0x3f))
                  cp' (- cp 0x10000)]
              (recur (+ i 4) (str out
                                  (char (+ 0xd800 (unsigned-bit-shift-right cp' 10)))
                                  (char (+ 0xdc00 (bit-and cp' 0x3ff))))))

            :else (recur (inc i) (str out (char b)))))))))

(defn ascii->bytes
  "Header fields (magic, version) are ASCII by definition."
  [s]
  (mapv char-code (seq s)))
