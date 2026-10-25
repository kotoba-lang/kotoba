(ns kasane.bytes
  "Portable read cursor over a sequence of unsigned byte values (0-255).
   Pure cljc — no host interop, so the same code runs on JVM, cljs and
   (the EDN-subset of) kotoba-clj → WASM.")

(defn cursor
  "Create a read cursor over `data` (anything seqable into 0-255 ints)."
  [data]
  (let [v (vec data)]
    {:data v :len (count v) :pos (atom 0)}))

(defn pos  [c] @(:pos c))
(defn len  [c] (:len c))
(defn eof? [c] (>= @(:pos c) (:len c)))
(defn seek! [c p] (reset! (:pos c) p) c)
(defn skip! [c n] (swap! (:pos c) + n) c)

(defn u8! [c]
  (let [p @(:pos c)]
    (when (>= p (:len c)) (throw (ex-info "kasane.bytes EOF" {:pos p :len (:len c)})))
    (reset! (:pos c) (inc p))
    (nth (:data c) p)))

(defn read-bytes!
  "Read `n` raw bytes, returning a vector of unsigned ints."
  [c n]
  (let [p @(:pos c) end (+ p n)]
    (when (> end (:len c)) (throw (ex-info "kasane.bytes EOF read-bytes" {:pos p :n n :len (:len c)})))
    (reset! (:pos c) end)
    (subvec (:data c) p end)))

(defn uint!
  "Read an `n`-byte unsigned integer. `big?` selects byte order."
  [c n big?]
  (let [bs (read-bytes! c n)
        bs (if big? bs (reverse bs))]
    (reduce (fn [acc b] (+ (* acc 256) b)) 0 bs)))

(defn- pow2
  "2^n via plain multiplication, not `bit-shift-left` — JS/cljs bitwise ops
   work on 32-bit signed ints with a mod-32 shift amount (`1 << 32` is `1`,
   not 4294967296, and `1 << 31` is negative), so `bit-shift-left` silently
   corrupts sign extension for n=32 on non-JVM cljc targets. This stays
   exact for n up to 53 (JS's safe-integer limit) — plenty for the i8/i16/
   i32 callers below (there is no :i64 grammar field type)."
  [n]
  (loop [i 0 acc 1] (if (= i n) acc (recur (inc i) (* acc 2)))))

(defn sint!
  "Read an `n`-byte two's-complement signed integer."
  [c n big?]
  (let [u    (uint! c n big?)
        bits (* 8 n)
        half (pow2 (dec bits))]
    (if (>= u half) (- u (pow2 bits)) u)))

(defn bytes->ascii
  "Interpret a seq of unsigned bytes as an ASCII/Latin-1 string."
  [bs]
  (apply str (map char bs)))
