(ns netconf.bytes
  "A small, portable UTF-8 codec bridging XML text (netconf.message /
  netconf.operations produce and consume strings) and the raw byte-seqs
  netconf.framing operates on (chunking is a byte-stream concern, per
  RFC 6242 §4.2 — see netconf.framing).

  Deliberately hand-rolled rather than `(map int (seq s))`: on
  ClojureScript, an element of `(seq s)` is a one-character STRING, not
  a code point, so `int` of it throws/misbehaves — this workspace's own
  org-modbus README records this exact idiom silently producing all-zero
  bytes under cljs, and notes it independently broke
  Sec-WebSocket-Accept in org-ietf-websocket and password hashing in
  org-ietf-argon2 the same day. This codec reads UTF-16 code units
  explicitly via `.charAt`/`.charCodeAt` (the one platform seam, isolated
  to `code-unit-at`/`code-unit->char` below) and does the surrogate-pair
  and UTF-8 arithmetic itself, so both platforms agree."
  )

(defn- code-unit-at [s i]
  #?(:clj (int (.charAt ^String s (int i)))
     :cljs (.charCodeAt s i)))

(defn- code-unit->char [cu]
  #?(:clj (char cu)
     :cljs (.fromCharCode js/String cu)))

(defn- code-points
  "UTF-16 string `s` -> a vector of Unicode code points, combining
  surrogate pairs (U+10000..U+10FFFF)."
  [s]
  (let [n (count s)]
    (loop [i 0 acc (transient [])]
      (if (>= i n)
        (persistent! acc)
        (let [cu (code-unit-at s i)]
          (if (and (<= 0xD800 cu) (<= cu 0xDBFF) (< (inc i) n))
            (let [lo (code-unit-at s (inc i))]
              (if (and (<= 0xDC00 lo) (<= lo 0xDFFF))
                (recur (+ i 2) (conj! acc (+ 0x10000 (bit-shift-left (- cu 0xD800) 10) (- lo 0xDC00))))
                (recur (inc i) (conj! acc cu))))
            (recur (inc i) (conj! acc cu))))))))

(defn- cp->code-units [cp]
  (if (< cp 0x10000)
    [cp]
    (let [cp' (- cp 0x10000)]
      [(+ 0xD800 (bit-shift-right cp' 10))
       (+ 0xDC00 (bit-and cp' 0x3FF))])))

(defn utf8-encode
  "String -> byte-seq (vector of ints 0..255), UTF-8."
  [s]
  (vec
    (mapcat
      (fn [cp]
        (cond
          (< cp 0x80)
          [cp]

          (< cp 0x800)
          [(bit-or 0xC0 (bit-shift-right cp 6))
           (bit-or 0x80 (bit-and cp 0x3F))]

          (< cp 0x10000)
          [(bit-or 0xE0 (bit-shift-right cp 12))
           (bit-or 0x80 (bit-and (bit-shift-right cp 6) 0x3F))
           (bit-or 0x80 (bit-and cp 0x3F))]

          :else
          [(bit-or 0xF0 (bit-shift-right cp 18))
           (bit-or 0x80 (bit-and (bit-shift-right cp 12) 0x3F))
           (bit-or 0x80 (bit-and (bit-shift-right cp 6) 0x3F))
           (bit-or 0x80 (bit-and cp 0x3F))]))
      (code-points s))))

(defn utf8-decode
  "byte-seq (ints 0..255) -> String, UTF-8. Never throws — malformed
  UTF-8 is the caller's data problem, not a reason for this function to
  throw. [:ok s] or [:error :utf8-malformed] (truncated/invalid
  continuation bytes, or a leading byte that doesn't head any valid
  UTF-8 sequence length)."
  [byte-seq]
  (let [bs (vec byte-seq)
        n (count bs)
        cont? (fn [i] (and (< i n) (= 0x80 (bit-and (nth bs i) 0xC0))))]
    (loop [i 0 cps (transient [])]
      (if (>= i n)
        [:ok (apply str (map code-unit->char (mapcat cp->code-units (persistent! cps))))]
        (let [b0 (nth bs i)]
          (cond
            (< b0 0x80)
            (recur (inc i) (conj! cps b0))

            (and (= 0xC0 (bit-and b0 0xE0)) (cont? (inc i)))
            (recur (+ i 2)
                   (conj! cps (bit-or (bit-shift-left (bit-and b0 0x1F) 6)
                                       (bit-and (nth bs (inc i)) 0x3F))))

            (and (= 0xE0 (bit-and b0 0xF0)) (cont? (inc i)) (cont? (+ i 2)))
            (recur (+ i 3)
                   (conj! cps (bit-or (bit-shift-left (bit-and b0 0x0F) 12)
                                       (bit-shift-left (bit-and (nth bs (inc i)) 0x3F) 6)
                                       (bit-and (nth bs (+ i 2)) 0x3F))))

            (and (= 0xF0 (bit-and b0 0xF8)) (cont? (inc i)) (cont? (+ i 2)) (cont? (+ i 3)))
            (recur (+ i 4)
                   (conj! cps (bit-or (bit-shift-left (bit-and b0 0x07) 18)
                                       (bit-shift-left (bit-and (nth bs (inc i)) 0x3F) 12)
                                       (bit-shift-left (bit-and (nth bs (+ i 2)) 0x3F) 6)
                                       (bit-and (nth bs (+ i 3)) 0x3F))))

            :else [:error :utf8-malformed]))))))
