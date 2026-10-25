(ns zip.bytes
  "Portable byte-level helpers over sequences of unsigned byte values (0–255).
   Pure cljc, deliberately self-contained so this repo depends on nothing but
   `org-ietf-deflate`.

   ZIP is little-endian throughout, mixes 16/32/64-bit fields, and stores member
   names in one of two character sets depending on a general-purpose flag bit —
   which is where most cross-tool ZIP bugs live, so name decoding is explicit
   here rather than implied."
  (:refer-clojure :exclude [bytes]))

;; ---------------------------------------------------------------------------
;; Little-endian integers
;; ---------------------------------------------------------------------------

(defn u8  [bv o] (nth bv o))
(defn u16 [bv o] (+ (nth bv o) (* 256 (nth bv (+ o 1)))))
(defn u32 [bv o]
  (+ (nth bv o) (* 256 (nth bv (+ o 1)))
     (* 65536 (nth bv (+ o 2))) (* 16777216 (nth bv (+ o 3)))))

(defn u64
  "ZIP64 fields are 8 bytes little-endian. Values beyond 2^53 cannot be
   represented exactly on a JavaScript runtime, so they are refused rather than
   silently rounded — a ZIP that large is out of scope for an in-memory reader
   anyway."
  [bv o]
  (let [lo (u32 bv o)
        hi (u32 bv (+ o 4))]
    (when (> hi 2097151)                                  ; 2^53 / 2^32
      (throw (ex-info "zip: 64-bit field exceeds exact integer range"
                      {:reason :too-large :offset o})))
    (+ lo (* hi 4294967296))))

;; ---------------------------------------------------------------------------
;; Names
;; ---------------------------------------------------------------------------

(defn bytes->ascii
  "Interpret a seq of unsigned bytes as an ASCII/Latin-1 string."
  [bs]
  (apply str (map char bs)))

(defn utf8->str
  "Decode UTF-8 bytes. A malformed sequence falls back to Latin-1 for that byte,
   so a mis-flagged archive degrades instead of throwing."
  [bs]
  (let [v (vec bs)
        n (count v)]
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
            ;; Outside the BMP: emit the surrogate pair.
            (let [cp  (bit-or (bit-shift-left (bit-and b 0x07) 18)
                              (bit-shift-left (bit-and (nth v (+ i 1)) 0x3f) 12)
                              (bit-shift-left (bit-and (nth v (+ i 2)) 0x3f) 6)
                              (bit-and (nth v (+ i 3)) 0x3f))
                  cp' (- cp 0x10000)]
              (recur (+ i 4) (str out
                                  (char (+ 0xd800 (unsigned-bit-shift-right cp' 10)))
                                  (char (+ 0xdc00 (bit-and cp' 0x3ff))))))

            :else (recur (inc i) (str out (char b)))))))))

(defn- char-code [c]
  #?(:clj (int c) :cljs (.charCodeAt c 0)))

(defn str->utf8
  "Encode a string as UTF-8 bytes. Surrogate pairs are combined, so non-BMP
   names round-trip."
  [s]
  (let [v (vec (seq s))
        n (count v)]
    (loop [i 0 out []]
      (if (>= i n)
        out
        (let [c (char-code (nth v i))]
          (cond
            (< c 0x80) (recur (inc i) (conj out c))

            (< c 0x800)
            (recur (inc i) (conj out (bit-or 0xc0 (unsigned-bit-shift-right c 6))
                                 (bit-or 0x80 (bit-and c 0x3f))))

            ;; high surrogate followed by a low surrogate
            (and (<= 0xd800 c 0xdbff) (< (inc i) n)
                 (<= 0xdc00 (char-code (nth v (inc i))) 0xdfff))
            (let [lo (char-code (nth v (inc i)))
                  cp (+ 0x10000 (bit-shift-left (- c 0xd800) 10) (- lo 0xdc00))]
              (recur (+ i 2) (conj out
                                   (bit-or 0xf0 (unsigned-bit-shift-right cp 18))
                                   (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 12) 0x3f))
                                   (bit-or 0x80 (bit-and (unsigned-bit-shift-right cp 6) 0x3f))
                                   (bit-or 0x80 (bit-and cp 0x3f)))))

            :else
            (recur (inc i) (conj out (bit-or 0xe0 (unsigned-bit-shift-right c 12))
                                 (bit-or 0x80 (bit-and (unsigned-bit-shift-right c 6) 0x3f))
                                 (bit-or 0x80 (bit-and c 0x3f))))))))))

;; ---------------------------------------------------------------------------
;; MS-DOS date and time (APPNOTE 4.4.6)
;; ---------------------------------------------------------------------------

(def dos-epoch
  "1980-01-01 00:00:00 — the earliest timestamp the MS-DOS fields can express,
   and what this repo writes by default so archives are reproducible."
  {:date 0x0021 :time 0x0000})

(defn dos->map [date time]
  {:year   (+ 1980 (unsigned-bit-shift-right date 9))
   :month  (bit-and (unsigned-bit-shift-right date 5) 0x0f)
   :day    (bit-and date 0x1f)
   :hour   (unsigned-bit-shift-right time 11)
   :minute (bit-and (unsigned-bit-shift-right time 5) 0x3f)
   :second (* 2 (bit-and time 0x1f))})

(defn map->dos [{:keys [year month day hour minute second]
                 :or   {year 1980 month 1 day 1 hour 0 minute 0 second 0}}]
  {:date (bit-or (bit-shift-left (max 0 (- year 1980)) 9)
                 (bit-shift-left month 5)
                 day)
   :time (bit-or (bit-shift-left hour 11)
                 (bit-shift-left minute 5)
                 (quot second 2))})
