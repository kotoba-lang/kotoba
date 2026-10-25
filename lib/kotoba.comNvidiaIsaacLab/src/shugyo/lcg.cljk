(ns shugyo.lcg
  "Shared deterministic LCG (linear congruential generator), ported from the two
  slightly different `Lcg` shapes duplicated across the original Rust crate
  (`dr.rs`, `cartpole_env.rs`, `vectorized_env.rs`, `reach_env.rs` — shared with
  `ee_reach_env.rs`/`policy.rs`): same multiplier/increment constants
  (`6364136223846793005` / `1442695040888963407`, the PCG32 constants), just
  different bit-extraction helpers on top (`next_f32_centered` for the two
  Cartpole envs, `next_signed` + `next_uniform` for `dr`/`reach`/`ee_reach`/
  `policy`). This namespace unifies both shapes into one portable module so
  every other `shugyo/*` namespace shares a single RNG implementation.

  u64 arithmetic honesty: `6364136223846793005` and `1442695040888963407` both
  fit under the maximum signed 64-bit value (2^63-1), so on the JVM the state
  is a primitive `long` and `unchecked-multiply`/`unchecked-add` wrap at 2^64
  in two's
  complement — bit-identical to Rust's `u64::wrapping_mul`/`wrapping_add`. JS
  numbers are IEEE-754 doubles (53 bits of exact integer precision) and cannot
  hold a 64-bit LCG state exactly, so the ClojureScript branch uses
  `goog.math.Long` (Google Closure's arbitrary-64-bit-integer emulation,
  bundled with every ClojureScript build — no extra dependency) to perform the
  same wrapping 64-bit multiply/add/unsigned-shift. Both branches produce the
  same *algorithm*; we do not assert bit-exact parity with the original Rust
  binary (the original Rust tests never assert that either — only
  same-seed-determinism and different-seed-divergence, which this port
  preserves on every platform).

  Public API is functional (state-in / value+state-out), matching the
  `kotoba-lang/cartpole-wasm` convention of returning `[value next-state]`
  pairs instead of Rust's `&mut self` mutation."
  #?(:cljs (:require [goog.math.Long :as gl])))

;; ---------------------------------------------------------------------------
;; Constants (PCG32 default multiplier/increment; identical across every Rust
;; `Lcg` shape in the original crate).
;; ---------------------------------------------------------------------------

#?(:clj
   (do
     (def ^:private MULT 6364136223846793005)
     (def ^:private INC 1442695040888963407)))

#?(:cljs
   (do
     (def ^:private MULT (.fromString gl/Long "6364136223846793005"))
     (def ^:private INC (.fromString gl/Long "1442695040888963407"))))

;; ---------------------------------------------------------------------------
;; Core step: state' = state * MULT + INC (mod 2^64)
;; ---------------------------------------------------------------------------

(defn lcg-step
  "Advance the raw 64-bit LCG state by one step (wrapping multiply-add)."
  [state]
  #?(:clj (unchecked-add (unchecked-multiply (long state) MULT) INC)
     :cljs (.add (.multiply state MULT) INC)))

(defn lcg-new
  "Scramble `seed` (any integer) into an initial LCG state, matching the Rust
  `Lcg::new(seed)` constructor (`seed.wrapping_mul(MULT).wrapping_add(INC)`)."
  [seed]
  #?(:clj (lcg-step (long seed))
     :cljs (lcg-step (.fromNumber gl/Long seed))))

;; ---------------------------------------------------------------------------
;; Bit extraction helpers
;; ---------------------------------------------------------------------------

(defn next-u01
  "Advance the state and return `[value state']` where `value` is uniform in
  `[0, 1)`. Mirrors the Rust `next_u01`: `(state >>> 33) as f32 / 2^31`."
  [state]
  (let [state' (lcg-step state)
        raw #?(:clj (unsigned-bit-shift-right (long state') 33)
               :cljs (.toNumber (.shiftRightUnsigned state' 33)))]
    [(/ (double raw) 2147483648.0) state']))

(defn next-signed
  "Advance the state and return `[value state']` where `value` is uniform in
  `[-1, 1)`. Mirrors the Rust `next_signed`: `(state >>> 40) as f32 / 2^24`,
  then `2u - 1`."
  [state]
  (let [state' (lcg-step state)
        raw #?(:clj (unsigned-bit-shift-right (long state') 40)
               :cljs (.toNumber (.shiftRightUnsigned state' 40)))
        u (/ (double raw) 16777216.0)]
    [(- (* 2.0 u) 1.0) state']))

(defn next-f32-centered
  "Advance the state and return `[value state']` where `value` is uniform in
  `[-half-range, half-range)`. Mirrors the Rust `next_f32_centered`."
  [state half-range]
  (let [[u01 state'] (next-u01 state)]
    [(* (- (* u01 2.0) 1.0) half-range) state']))

(defn next-uniform
  "Advance the state and return `[value state']` where `value` is uniform in
  `[low, high)`. Mirrors the Rust `next_uniform`."
  [state low high]
  (let [[u01 state'] (next-u01 state)]
    [(+ low (* (- high low) u01)) state']))
