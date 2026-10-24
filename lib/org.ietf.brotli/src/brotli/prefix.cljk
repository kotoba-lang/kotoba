(ns brotli.prefix
  "Prefix (Huffman) codes as brotli stores them (RFC 7932 §3).

   The codes themselves are canonical and assigned exactly as in DEFLATE — count
   lengths, derive the first code of each length, hand them out in symbol order —
   so decoding walks bit by bit with each new bit shifted in at the bottom.

   What is brotli-specific is the *description*:

   - a **simple** code (§3.4) lists 1-4 symbols outright, with fixed length
     patterns and a tree-select bit for the four-symbol case;
   - a **complex** code (§3.5) transmits code lengths for the 18-symbol
     code-length alphabet in a fixed non-sequential order, each using a
     hand-rolled 2-4 bit code, and then the real code lengths using *that*,
     with two repeat mechanisms (16 repeats the previous non-zero length, 17
     repeats zeros) whose counts *accumulate* when the same repeat code appears
     twice in a row.

   That accumulation is the subtle part: `7, 16(+3), 16(+2)` is not 3 then 4
   repeats, it is one run whose count is recomputed as
   `4 * (count - 2) + newly read`."
  (:require [brotli.bits :as bits]))

(def ^:private code-length-order
  "§3.5: the order in which the code-length alphabet's own lengths arrive."
  [1 2 3 4 0 5 17 6 16 7 8 9 10 11 12 13 14 15])

(defn decode-table
  "Canonical decode table from per-symbol code lengths: `{[len code] symbol}`
   plus the longest length. A single-symbol code has length 0 and consumes no
   bits, which brotli allows and relies on."
  [lengths]
  (let [maxlen   (reduce max 0 lengths)
        used     (keep-indexed (fn [i l] (when (pos? l) i)) lengths)
        bl-count (reduce (fn [m l] (if (pos? l) (update m l (fnil inc 0)) m)) {} lengths)
        next-code (loop [len 1 code 0 acc {}]
                    (if (> len maxlen)
                      acc
                      (let [code (bit-shift-left (+ code (get bl-count (dec len) 0)) 1)]
                        (recur (inc len) code (assoc acc len code)))))]
    ;; §3.4/§3.5: a code with exactly one used symbol emits and consumes *no
    ;; bits* — the symbol is simply returned. Treating it as a one-bit code makes
    ;; every stream that contains one (a literal alphabet where every byte has the
    ;; same probability, for instance) fail at the first symbol.
    (if (= 1 (count used))
      {:single (first used) :maxlen 0}
      (loop [syms used nc next-code t (transient {})]
        (if-not (seq syms)
          {:table (persistent! t) :maxlen maxlen}
          (let [s (first syms)
                l (nth lengths s)]
            (recur (next syms) (update nc l inc) (assoc! t [l (get nc l)] s))))))))

(defn read-sym
  "Decode one symbol. A code built from a single symbol reads no bits."
  [r {:keys [table maxlen single]}]
  (if single
    single
    (loop [len 1 code 0]
      (let [code (bit-or (bit-shift-left code 1) (bits/read-bit r))]
        (if-let [s (get table [len code])]
          s
          (do (when (>= len maxlen)
                (throw (ex-info "brotli: invalid prefix code"
                                {:reason :bad-prefix-code :len len})))
              (recur (inc len) code)))))))

;; ---------------------------------------------------------------------------
;; Reading a code description
;; ---------------------------------------------------------------------------

(defn- alphabet-bits
  "The smallest width that can hold any symbol of the alphabet (§3.4)."
  [alphabet-size]
  (loop [b 1] (if (>= (bit-shift-left 1 b) alphabet-size) b (recur (inc b)))))

(defn- read-simple
  "§3.4: 1-4 symbols listed outright."
  [r alphabet-size]
  (let [nsym (inc (bits/read-bits r 2))
        abits (alphabet-bits alphabet-size)
        syms (vec (repeatedly nsym #(bits/read-bits r abits)))]
    (when (some #(>= % alphabet-size) syms)
      (throw (ex-info "brotli: simple prefix code names a symbol outside the alphabet"
                      {:reason :bad-prefix-code :symbols syms :alphabet alphabet-size})))
    (when (not= (count syms) (count (set syms)))
      (throw (ex-info "brotli: simple prefix code repeats a symbol"
                      {:reason :bad-prefix-code :symbols syms})))
    (if (= nsym 1)
      {:single (first syms) :maxlen 0}
      (let [lens (case nsym
                 1 [0]
                 2 [1 1]
                 3 [1 2 2]
                 4 (if (pos? (bits/read-bit r)) [1 2 3 3] [2 2 2 2]))
            lengths (persistent!
                     (reduce (fn [v [s l]] (assoc! v s l))
                             (transient (vec (repeat alphabet-size 0)))
                             (map vector syms lens)))]
        (decode-table lengths)))))

(defn- read-code-length-code-length
  "The hand-rolled 2-4 bit code for the code-length alphabet's own lengths
   (§3.5). Patterns are written MSB-left in the RFC but read LSB-first."
  [r]
  (let [two (bits/read-bits r 2)]
    (case two
      0 0
      1 4
      2 3
      3 (if (zero? (bits/read-bit r))
          2
          (if (zero? (bits/read-bit r)) 1 5)))))

(defn- read-complex
  "§3.5: code lengths for the code-length alphabet, then the real code lengths."
  [r hskip alphabet-size]
  (let [;; Lengths for the 18-symbol code-length alphabet, in the fixed order,
        ;; stopping as soon as the space is filled.
        [cl-lengths]
        (loop [i hskip
               lengths (vec (repeat 18 0))
               space 0
               nonzero 0]
          (if (or (>= i 18) (>= space 32))
            [lengths]
            (let [l (read-code-length-code-length r)
                  sym (nth code-length-order i)
                  lengths (assoc lengths sym l)]
              (if (pos? l)
                (recur (inc i) lengths (+ space (quot 32 (bit-shift-left 1 l))) (inc nonzero))
                (recur (inc i) lengths space nonzero)))))
        cl-table (decode-table cl-lengths)
        ;; Now the real code lengths. Codes 16/17 repeat the previous non-zero
        ;; length / zeros, and a *second* one of the same kind in a row replaces
        ;; the run total rather than adding to it: only the delta is appended.
        lengths
        (loop [out (vec (repeat alphabet-size 0))
               i 0
               prev-len 8
               repeat-n 0
               repeat-len 0
               space 0]
          (if (or (>= i alphabet-size) (>= space 32768))
            out
            (let [sym (read-sym r cl-table)]
              (if (< sym 16)
                (recur (assoc out i sym) (inc i)
                       (if (pos? sym) sym prev-len)
                       0 0
                       (if (pos? sym) (+ space (quot 32768 (bit-shift-left 1 sym))) space))
                (let [extra   (- sym 14)                    ; 2 for 16, 3 for 17
                      new-len (if (= sym 16) prev-len 0)
                      ;; The run only continues if it repeats the same length.
                      [carry rlen] (if (= repeat-len new-len) [repeat-n new-len] [0 new-len])
                      total   (+ (if (pos? carry) (bit-shift-left (- carry 2) extra) 0)
                                 (bits/read-bits r extra) 3)
                      delta   (- total carry)]
                  (when (> (+ i delta) alphabet-size)
                    (throw (ex-info "brotli: code length repeat runs past the alphabet"
                                    {:reason :bad-prefix-code :at i :delta delta})))
                  (recur (reduce (fn [v k] (assoc v (+ i k) new-len)) out (range delta))
                         (+ i delta) prev-len total rlen
                         (if (pos? new-len)
                           (+ space (* delta (quot 32768 (bit-shift-left 1 new-len))))
                           space)))))))
        _ (when (< (count (filter pos? lengths)) 1)
            (throw (ex-info "brotli: prefix code has no symbols"
                            {:reason :bad-prefix-code})))]
    (when (and (> (count (filter pos? lengths)) 1)
               (not= 32768 (reduce + (map #(if (pos? %) (quot 32768 (bit-shift-left 1 %)) 0)
                                          lengths))))
      (throw (ex-info "brotli: prefix code lengths are not a complete tree"
                      {:reason :bad-prefix-code
                       :space (reduce + (map #(if (pos? %) (quot 32768 (bit-shift-left 1 %)) 0)
                                             lengths))})))
    (decode-table lengths)))

(defn read-code
  "Read one prefix code description over an alphabet of `alphabet-size` symbols
   and return its decode table."
  [r alphabet-size]
  (let [hskip (bits/read-bits r 2)]
    (if (= hskip 1)
      (read-simple r alphabet-size)
      (read-complex r hskip alphabet-size))))
