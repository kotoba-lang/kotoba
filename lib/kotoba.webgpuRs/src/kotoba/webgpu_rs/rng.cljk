(ns kotoba.webgpu-rs.rng
  "Deterministic xorshift32 PRNG — the exact 32-bit xorshift kami-webgpu-rs
  used (seed `2654435769`, the Rust `u32` overflow-wrapping `^=`/`<<`/`>>`
  sequence) to scatter demo-city props and `scene_to_ir` buildings/trees
  so the web (CLJS) and native (Rust, now this cljc port) renderers agree
  on the same procedurally-generated world from the same EDN. Ported
  verbatim: same seed, same shift constants, same `& 0x7fffffff` /
  `2147483647.0` normalization to `[0,1)`.

  No network, no I/O.")

(def ^:const default-seed
  "The fixed seed kami-webgpu-rs's `scene_to_ir` and `demo_city` both use."
  2654435769)

(def ^:const u32-mask 0xffffffff)

(defn- wrap32 [n] (bit-and n u32-mask))

(defn next-state
  "Advance one xorshift32 step: `s ^= s<<13; s ^= s>>17; s ^= s<<5;` with
  32-bit wraparound at every step (Rust `u32` semantics)."
  [seed]
  (let [s1 (wrap32 (bit-xor seed (wrap32 (bit-shift-left seed 13))))
        s2 (wrap32 (bit-xor s1 (unsigned-bit-shift-right s1 17)))
        s3 (wrap32 (bit-xor s2 (wrap32 (bit-shift-left s2 5))))]
    s3))

(defn value
  "The `[0,1)` float a xorshift32 `state` yields: `(state & 0x7fffffff) /
  2147483647.0`."
  [state]
  (/ (double (bit-and state 0x7fffffff)) 2147483647.0))

(defn make
  "A lazy, infinite sequence of `[0,1)` floats from `seed` (default
  [[default-seed]]), one xorshift32 step apart — the cljc equivalent of
  kami-webgpu-rs's `let mut rnd = || {...}` mutable closure. Callers thread
  through it with `next`/`rest` (or destructure the head) instead of
  mutating a captured `seed` var, since idiomatic Clojure prefers explicit
  state threading over hidden mutation."
  ([] (make default-seed))
  ([seed]
   (let [s (next-state seed)]
     (cons (value s) (lazy-seq (make s))))))
