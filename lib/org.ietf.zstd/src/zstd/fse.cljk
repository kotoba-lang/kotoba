(ns zstd.fse
  "Finite State Entropy decoding (RFC 8878 §4.1) — the entropy coder zstd uses for
   sequence codes and for Huffman weights.

   FSE is a tANS coder: a state indexes a table that yields a symbol plus how many
   bits to read to reach the next state. Two things about it are easy to get
   subtly wrong and hard to notice:

   1. **The table description is read forward, LSB-first**, while the data it
      later decodes is read *backward*, MSB-first (`zstd.bits`).
   2. **A count of -1 means \"low probability\"**: that symbol occupies a single
      slot taken from the *end* of the table, and the spread loop must skip those
      slots. Ignore it and the table looks plausible but assigns the wrong symbols
      to high states, which only shows up on inputs that reach them."
  (:require [zstd.bits :as bits]))

;; ---------------------------------------------------------------------------
;; Table description
;; ---------------------------------------------------------------------------

(defn- peek-bits [r n]
  (let [p (bits/fwd-bit-pos r)
        v (bits/fwd-bits r n)]
    (bits/fwd-seek! r p)
    v))

(defn- renormalize
  "After each count, the field width shrinks while the remaining probability
   fits in a smaller threshold."
  [remaining threshold nb-bits]
  (loop [th threshold nb nb-bits]
    (if (< remaining th)
      (recur (unsigned-bit-shift-right th 1) (dec nb))
      [th nb])))

(defn read-ncount
  "Read a normalized-count table description starting at byte `from`.

   Returns `{:counts [...] :accuracy-log n :end <byte offset past the table>}`."
  [data from max-symbol]
  (let [r  (bits/fwd-reader data from)
        al (+ 5 (bits/fwd-bits r 4))]
    (when (> al 9)
      (throw (ex-info "zstd: FSE accuracy log is out of range"
                      {:reason :bad-fse-table :accuracy-log al})))
    (loop [counts    []
           remaining (inc (bit-shift-left 1 al))
           threshold (bit-shift-left 1 al)
           nb-bits   (inc al)
           previous0 false]
      (cond
        (or (<= remaining 1) (> (count counts) max-symbol))
        ;; `fwd-bit-pos` is absolute (the reader starts at `from` * 8), so the
        ;; end is that rounded up to a byte — adding `from` back would double it.
        {:counts counts
         :accuracy-log al
         :end (quot (+ (bits/fwd-bit-pos r) 7) 8)}

        previous0
        ;; A run of zero-probability symbols, in groups of two bits; 3 means
        ;; "three more, and keep reading".
        (let [n0 (loop [n 0]
                   (let [two (bits/fwd-bits r 2)]
                     (if (= two 3) (recur (+ n 3)) (+ n two))))]
          (recur (into counts (repeat n0 0)) remaining threshold nb-bits false))

        :else
        (let [max*   (- (dec (* 2 threshold)) remaining)
              low    (peek-bits r (dec nb-bits))
              count* (if (< low max*)
                       (do (bits/fwd-bits r (dec nb-bits)) low)
                       (let [full (peek-bits r nb-bits)]
                         (bits/fwd-bits r nb-bits)
                         (if (>= full threshold) (- full max*) full)))
              c      (dec count*)
              remaining* (- remaining (if (neg? c) (- c) c))
              [th nb] (renormalize remaining* threshold nb-bits)]
          (recur (conj counts c) remaining* th nb (zero? c)))))))

;; ---------------------------------------------------------------------------
;; Decoding table
;; ---------------------------------------------------------------------------

(defn- highbit32 [x]
  (loop [i 31]
    (cond (neg? i) 0
          (pos? (bit-and x (bit-shift-left 1 i))) i
          :else (recur (dec i)))))

(defn build-table
  "Build a decode table from normalized `counts`.

   Returns a vector of `{:symbol s :nb-bits n :new-state s'}`, indexed by state."
  [counts accuracy-log]
  (let [table-size (bit-shift-left 1 accuracy-log)
        mask       (dec table-size)
        step       (+ (unsigned-bit-shift-right table-size 1)
                      (unsigned-bit-shift-right table-size 3)
                      3)
        ;; "Low probability" symbols (-1) take slots from the top, downward.
        [symbols high-threshold next0]
        (reduce (fn [[syms ht nxt] [s c]]
                  (if (= c -1)
                    [(assoc syms ht s) (dec ht) (assoc nxt s 1)]
                    [syms ht (assoc nxt s c)]))
                [(vec (repeat table-size nil)) (dec table-size) {}]
                (map-indexed vector counts))
        ;; Everything else is spread across the remaining slots.
        symbols
        (first
         (reduce
          (fn [[syms pos] [s c]]
            (if (or (= c -1) (<= c 0))
              [syms pos]
              (loop [i 0 syms syms pos pos]
                (if (= i c)
                  [syms pos]
                  (let [syms (assoc syms pos s)
                        pos  (loop [p (bit-and (+ pos step) mask)]
                               (if (> p high-threshold)
                                 (recur (bit-and (+ p step) mask))
                                 p))]
                    (recur (inc i) syms pos))))))
          [symbols 0]
          (map-indexed vector counts)))]
    (when (some nil? symbols)
      (throw (ex-info "zstd: FSE table description does not fill its table"
                      {:reason :bad-fse-table})))
    (first
     (reduce (fn [[table nxt] u]
               (let [s     (nth symbols u)
                     state (get nxt s)
                     nb    (- accuracy-log (highbit32 state))
                     new-s (- (* state (bit-shift-left 1 nb)) table-size)]
                 [(conj table {:symbol s :nb-bits nb :new-state new-s})
                  (assoc nxt s (inc state))]))
             [[] next0]
             (range table-size)))))

;; ---------------------------------------------------------------------------
;; Decoder over a backward bitstream
;; ---------------------------------------------------------------------------

(defn init-state
  "The initial state is `accuracy-log` bits read from the front of the (backward)
   stream."
  [r accuracy-log]
  (bits/rev-bits r accuracy-log))

(defn symbol-at [table state]
  (:symbol (nth table state)))

(defn next-state
  "Advance a state by reading its table entry's bit count."
  [r table state]
  (let [{:keys [nb-bits new-state]} (nth table state)]
    (+ new-state (bits/rev-bits r nb-bits))))

;; ---------------------------------------------------------------------------
;; Predefined distributions (RFC 8878 §3.1.1.3.2.2.1)
;; ---------------------------------------------------------------------------

(def literal-length-default
  {:accuracy-log 6
   :counts [4 3 2 2 2 2 2 2 2 2 2 2 2 1 1 1
            2 2 2 2 2 2 2 2 2 3 2 1 1 1 1 1
            -1 -1 -1 -1]})

(def match-length-default
  ;; Note the tail: codes 46-52 are all low-probability (-1), i.e. *seven*
  ;; entries, not five. A wrong split here still sums to 64, so the table builds
  ;; without complaint and decodes plausibly until a state in the affected range
  ;; comes up — which is exactly how this was found.
  {:accuracy-log 6
   :counts [1 4 3 2 2 2 2 2 2 1 1 1 1 1 1 1
            1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
            1 1 1 1 1 1 1 1 1 1 1 1 1 1 -1 -1
            -1 -1 -1 -1 -1]})

(def offset-default
  {:accuracy-log 5
   :counts [1 1 1 1 1 1 2 2 2 1 1 1 1 1 1 1
            1 1 1 1 1 1 1 1 -1 -1 -1 -1 -1]})

(def ^:private ll-extra
  [1 1 1 1 2 2 3 3 4 6 7 8 9 10 11 12 13 14 15 16])

(def ^:private ml-extra
  [1 1 1 1 2 2 3 3 4 4 5 7 8 9 10 11 12 13 14 15 16])

(defn- baselines
  "Codes above the direct range have a baseline that advances by 2^extra-bits."
  [start extras]
  (first (reduce (fn [[acc base] e] [(conj acc base) (+ base (bit-shift-left 1 e))])
                 [[] start] extras)))

(def literal-length-code
  "Code → `[baseline extra-bits]` (RFC 8878 §3.1.1.3.2.1.1)."
  (into (mapv (fn [c] [c 0]) (range 16))
        (mapv vector (baselines 16 ll-extra) ll-extra)))

(def match-length-code
  (into (mapv (fn [c] [(+ c 3) 0]) (range 32))
        (mapv vector (baselines 35 ml-extra) ml-extra)))

(def ^:private pow2 (vec (reductions * 1 (repeat 32 2))))

(defn offset-code
  "Offset code N encodes values `2^N .. 2^(N+1)-1` with N extra bits. Uses a
   power table rather than a shift: code 31 would be negative in int32."
  [n]
  [(nth pow2 n) n])
