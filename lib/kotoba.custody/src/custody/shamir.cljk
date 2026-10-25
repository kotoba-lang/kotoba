(ns custody.shamir
  "Shamir secret sharing over GF(2^8) — split one secret into `n` shares of
  which any `m` reconstruct it, and any `m-1` reveal nothing.

  Pure `.cljc` arithmetic. It holds no randomness and no hash: `split` takes
  a `rand-bytes-fn` and the caller carries the digest, because a portable
  namespace cannot honestly claim a secure RNG on every runtime this
  workspace targets, and a library that silently falls back to `rand-int`
  would be worse than one that refuses to have an opinion.

  Byte-wise: each byte of the secret is an independent polynomial whose
  constant term is that byte, evaluated at x = 1..n. That is the standard
  construction (the one `age`'s and Vault's share formats use) and it is
  information-theoretically secure per byte — see the `m-1` test, which
  does not assert this by assertion but by exhibiting the bijection.

  Two things it does NOT hide, stated here so nobody has to discover them
  from an incident:

  - **length**. Every share is exactly as long as the secret. Splitting a
    passphrase tells every custodian how long it is. Pad before splitting
    if that matters.
  - **wrongness**. Shamir is malleable: combine the wrong shares, or a
    share with one byte flipped, and you get a different secret rather
    than an error. There is no redundancy in the algebra to notice with.
    That is what `custody.model`'s `:deal/secret-digest` is for, and why
    `combine` here is deliberately the unverified primitive — the verified
    path lives next to the thing that carries the digest."
  (:refer-clojure :exclude [split]))

;; --------------------------------------------------------------- GF(2^8)

(defn- xtime
  "Multiply by x in GF(2^8) with the AES reducing polynomial
  x^8 + x^4 + x^3 + x + 1 (0x11b)."
  [a]
  (let [s (bit-shift-left a 1)]
    (bit-and 0xff (if (pos? (bit-and a 0x80)) (bit-xor s 0x1b) s))))

(def ^:private tables
  ;; exp/log against generator 3 (= x + 1, a generator of the multiplicative
  ;; group). exp is stored doubled so an index sum up to 508 needs no `mod`
  ;; in the hot path.
  (loop [i 0, x 1, exp [], log (vec (repeat 256 0))]
    (if (= i 255)
      {:exp (into exp exp) :log log}
      (recur (inc i)
             (bit-xor (xtime x) x)
             (conj exp x)
             (assoc log x i)))))

(defn gf-add
  "Addition in GF(2^8) is XOR — and so is subtraction, which is why
  `combine` never needs a negation."
  [a b]
  (bit-xor a b))

(defn gf-mul [a b]
  (if (or (zero? a) (zero? b))
    0
    (let [{:keys [exp log]} tables]
      (nth exp (+ (nth log a) (nth log b))))))

(defn gf-div [a b]
  (when (zero? b)
    (throw (ex-info "division by zero in GF(2^8)" {:custody/error :gf-div-zero})))
  (if (zero? a)
    0
    (let [{:keys [exp log]} tables]
      (nth exp (+ (nth log a) (- 255 (nth log b)))))))

;; ----------------------------------------------------------------- split

(defn- eval-poly
  "Horner evaluation of a polynomial (coefficients low-order first) at `x`."
  [coeffs x]
  (reduce (fn [acc c] (gf-add (gf-mul acc x) c))
          0
          (reverse coeffs)))

(def max-shares
  "x = 0 is the secret itself, so the usable evaluation points are 1..255."
  255)

(defn split-error
  "Why this split would be refused, or nil. Separated from `split` so a
  caller can check a proposed (m, n) before it holds any secret bytes."
  [secret-bytes threshold total]
  (cond
    (not (sequential? secret-bytes)) :secret-not-sequential
    (empty? secret-bytes) :secret-empty
    (not (every? #(and (integer? %) (<= 0 % 255)) secret-bytes)) :secret-not-bytes
    (not (integer? threshold)) :threshold-not-integer
    (not (integer? total)) :total-not-integer
    (< threshold 2) :threshold-below-2
    (> threshold total) :threshold-above-total
    (> total max-shares) :total-above-255
    :else nil))

(defn shares-needed-random-bytes
  "How many random bytes `split` will draw. Exposed so a caller can source
  them in one syscall and so tests can inject exactly the right length."
  [secret-bytes threshold]
  (* (count secret-bytes) (dec threshold)))

(defn split
  "Split `secret-bytes` (a seq of unsigned bytes) into `total` shares with
  reconstruction threshold `threshold`.

  `rand-bytes-fn` is called ONCE with the byte count from
  `shares-needed-random-bytes` and must return that many uniformly random
  bytes. One call rather than one per byte on purpose: it makes the
  randomness a single auditable input, and it makes a deterministic
  injection in tests a flat vector instead of a call-order puzzle.

  Returns `[{:share/x 1 :share/y [...]} ...]`, x ascending from 1. Threshold
  is NOT recorded on the share — a share that carried its own threshold
  would invite trusting an attacker-supplied one. It lives in the deal
  (`custody.model`), which is signed."
  [secret-bytes threshold total rand-bytes-fn]
  (when-let [e (split-error secret-bytes threshold total)]
    (throw (ex-info "invalid shamir split" {:custody/error e
                                            :threshold threshold
                                            :total total})))
  (let [secret (vec secret-bytes)
        want (shares-needed-random-bytes secret threshold)
        rnd (vec (rand-bytes-fn want))]
    (when (not= want (count rnd))
      (throw (ex-info "rand-bytes-fn returned the wrong length"
                      {:custody/error :bad-randomness
                       :wanted want :got (count rnd)})))
    (when-not (every? #(and (integer? %) (<= 0 % 255)) rnd)
      (throw (ex-info "rand-bytes-fn returned non-bytes"
                      {:custody/error :bad-randomness})))
    (let [k (dec threshold)
          polys (mapv (fn [i]
                        (into [(nth secret i)]
                              (subvec rnd (* i k) (* (inc i) k))))
                      (range (count secret)))]
      (mapv (fn [x] {:share/x x
                     :share/y (mapv #(eval-poly % x) polys)})
            (range 1 (inc total))))))

;; --------------------------------------------------------------- combine

(defn combine-error
  [shares]
  (let [xs (mapv :share/x shares)
        lens (into #{} (map (comp count :share/y)) shares)]
    (cond
      (not (sequential? shares)) :shares-not-sequential
      (< (count shares) 2) :too-few-shares
      (not (every? #(and (integer? %) (<= 1 % max-shares)) xs)) :share-x-out-of-range
      (not= (count xs) (count (set xs))) :duplicate-share-x
      (not= 1 (count lens)) :share-length-mismatch
      :else nil)))

(defn combine
  "Reconstruct the secret from `shares` by Lagrange interpolation at x = 0.

  UNVERIFIED. Given fewer than the threshold, or shares from two different
  deals that happen to be the same length, this returns a plausible-looking
  byte vector that is not the secret, and it cannot tell. Prefer
  `custody.model/open` unless you are certain you have the right quorum and
  are checking the result yourself."
  [shares]
  (when-let [e (combine-error shares)]
    (throw (ex-info "invalid shamir combine" {:custody/error e})))
  (let [shares (vec shares)
        xs (mapv :share/x shares)
        n (count (:share/y (first shares)))
        ;; Lagrange basis at 0: for share j, Π_{i≠j} x_i / (x_i - x_j),
        ;; and subtraction is XOR.
        basis (mapv (fn [j]
                      (let [xj (nth xs j)]
                        (reduce (fn [acc i]
                                  (if (= i j)
                                    acc
                                    (let [xi (nth xs i)]
                                      (gf-mul acc (gf-div xi (gf-add xi xj))))))
                                1
                                (range (count xs)))))
                    (range (count xs)))]
    (mapv (fn [b]
            (reduce (fn [acc j]
                      (gf-add acc (gf-mul (nth (:share/y (nth shares j)) b)
                                          (nth basis j))))
                    0
                    (range (count shares))))
          (range n))))
