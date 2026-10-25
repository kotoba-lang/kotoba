(ns game.common
  "Shared utilities for kami-game: deterministic PRNG, HP trait.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/common.rs`:
  a xorshift32 deterministic PRNG used across NPC AI, battle systems,
  gacha, and terrain generation.")

;; -----------------------------------------------------------------------
;; SimpleRng — deterministic xorshift32 PRNG, zero allocation.
;;
;; Represented as a plain map {:seed <uint32>}. All operations are pure
;; functions that return a new state map (never mutate in place), mirroring
;; Rust's `&mut self` methods.
;; -----------------------------------------------------------------------

(def ^:const u32-max 4294967295)

(defn- ->u32
  "Mask an integer down to unsigned 32-bit range."
  [n]
  (bit-and n 0xFFFFFFFF))

(defn rng-new
  "Create a new SimpleRng state from `seed`. Seed 0 is coerced to 1
  (xorshift cannot recover from an all-zero state)."
  [seed]
  {:seed (->u32 (if (zero? seed) 1 seed))})

(defn rng-next-f32
  "Advance the RNG and return [new-state pseudo-random-f32-in-0-1)."
  [{:keys [seed]}]
  (let [s1 (->u32 (bit-xor seed (->u32 (bit-shift-left seed 13))))
        s2 (->u32 (bit-xor s1 (unsigned-bit-shift-right s1 17)))
        s3 (->u32 (bit-xor s2 (->u32 (bit-shift-left s2 5))))
        v  (Math/abs (double (/ s3 u32-max)))]
    [{:seed s3} v]))

(defn rng-range
  "Advance the RNG and return [new-state pseudo-random-f32-in-min-max)]."
  [rng min max]
  (let [[rng' f] (rng-next-f32 rng)]
    [rng' (+ min (* f (- max min)))]))

(defn rng-next-u32
  "Advance the RNG and return [new-state pseudo-random-u32-in-0-max)]."
  [rng max]
  (let [[rng' f] (rng-next-f32 rng)]
    [rng' (long (* f max))]))

(defn rng-chance
  "Advance the RNG and return [new-state bool] true with probability
  `probability` (0.0-1.0)."
  [rng probability]
  (let [[rng' f] (rng-next-f32 rng)]
    [rng' (< f probability)]))
