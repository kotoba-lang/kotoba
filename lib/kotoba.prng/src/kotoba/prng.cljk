(ns kotoba.prng
  "Deterministic discrete PRNG answering the same on every host.

  A 64-bit linear congruential generator (PCG32's default multiplier/increment:
  6364136223846793005 / 1442695040888963407), seeded once and advanced purely
  functionally. The same seed produces the same word stream on the JVM and in
  ClojureScript, which is what seeded search and test workloads depend on.

  This mirrors the shared LCG shape first proven portable in
  `com-nvidia-isaac-lab`'s `shugyo.lcg`, generalised to a kotoba-lang lib and
  focused on integer draws.

  ## Why not a cryptographic RNG

  `capability-random-bytes` owns *unpredictable* bytes (keys/nonces). This
  namespace is the opposite: deterministic, seeded, reproducible -- for tests,
  search, simulations. Never the two.

  ## 64-bit portability

  `state * 6364136223846793005 + 1442695040888963407` wraps at 2^64. On the JVM
  that is primitive `long` unchecked wrap. In ClojureScript a JS `BigInt`
  (arbitrary precision) carries the state; ClojureScript's `*`/`+`/`bit-and`
  operate on BigInt directly (no double rounding), then `>> 32` yields the top
  32 bits. Both branches run the same algorithm."
  (:refer-clojure :exclude [next]))

;; ---------------------------------------------------------------------------
;; The 64-bit LCG (PCG32 default multiplier/increment, as shugyo.lcg).
;; ---------------------------------------------------------------------------

#?(:clj
   (def ^:private MULT 6364136223846793005))
#?(:cljs
   (def ^:private MULT (js/BigInt "6364136223846793005")))

#?(:clj
   (def ^:private INC 1442695040888963407))
#?(:cljs
   (def ^:private INC (js/BigInt "1442695040888963407")))

(defn seed-state
  "Scramble `seed` (any integer) into the initial 64-bit state."
  [seed]
  #?(:clj  (unchecked-add (unchecked-multiply (long seed) MULT) INC)
     :cljs (+ (* (js/BigInt seed) MULT) INC)))

(defn step-state
  "Advance `state` by one (wrapping 64-bit multiply-add); returns the new state."
  [state]
  #?(:clj  (unchecked-add (unchecked-multiply (long state) MULT) INC)
     :cljs (+ (* (js/BigInt state) MULT) INC)))

(defn word-32
  "Advance the state and return `[word state']` where `word` is a 32-bit
  draw in `[0, 2^32)` — the LOW 32 bits of the advanced state, identical on
  every host (BigInt-exact in ClojureScript)."
  [state]
  (let [state' (step-state state)]
    [#?(:clj (bit-and (long state') 0xFFFFFFFF)
        :cljs (js/Number (js/BigInt.asUintN 32 (js/BigInt state'))))
     state']))

(defn next-int
  "Advance the state and return `[value state']` with `value` uniform in
  `[0, bound)` for a POSITIVE `bound`, as `(word-32 state)` mod `bound`."
  [state bound]
  (if (<= (long bound) 0)
    (throw (js/Error. "next-int requires a positive bound"))
    (let [[w state'] (word-32 state)]
      [(mod w (long bound)) state'])))