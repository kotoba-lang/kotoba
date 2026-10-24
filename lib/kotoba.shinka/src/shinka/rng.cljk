(ns shinka.rng
  "Deterministic, portable, splittable PRNG for `shinka`.

  The state is a plain value and every draw returns `[value state']` rather
  than mutating, so the same seed replays the same evolutionary run -- on the
  JVM and on ClojureScript alike. A run that cannot be replayed is not
  evidence, it is an anecdote.

  ## Why xorshift32 and not a 64-bit generator

  A 64-bit LCG is the obvious choice and was written first. It was thrown
  away: `js/Number` cannot hold 64 bits, so the ClojureScript branch had to
  emulate the multiply with 16-bit limbs, and the claim \"both hosts produce
  the same stream\" then rests on hand-rolled arithmetic that is easy to get
  subtly wrong and expensive to prove right.

  xorshift32 uses only shifts and xor. With one `u32` helper per host the two
  branches are the *same* operations on the same 32-bit values, so parity is
  structural rather than asserted -- and `rng-test` pins the first draws as
  literals so a host that ever disagrees fails loudly.

  What this costs, stated plainly: period 2^32-1, and it is not a
  cryptographic generator. For population search -- where the requirement is
  reproducibility and decorrelation between individuals, not unpredictability
  -- that is enough. If a run ever needs more than ~4x10^9 draws, this is the
  wrong generator and the failure will be silent, so `shinka.evolve` records
  the draw count it consumed.

  ## Why this does not depend on `shugyo.lcg`

  `kotoba-lang/com-nvidia-isaac-lab` ships an LCG of exactly this shape and
  reusing it was considered first. Rejected on dependency *direction*: a
  general population-search library must not require an Isaac-Lab-compatible
  RL framework to draw a random number. `shugyo.policy` makes the mirror-image
  note about its own original (`policy.rs` imported `Lcg` from `reach_env`,
  and the CLJC port moved it out precisely to break that edge)."
  (:refer-clojure :exclude [seed]))

(defn- u32
  "Coerce to an unsigned 32-bit integer in `[0, 2^32)`.

  The single place the two hosts differ. On the JVM values are longs, so a
  mask suffices; in ClojureScript bitops are already 32-bit but signed, so
  `>>> 0` is what reinterprets the sign bit."
  [x]
  #?(:clj  (bit-and x 0xFFFFFFFF)
     :cljs (unsigned-bit-shift-right x 0)))

(defn seed
  "An RNG state from an integer `n`. Distinct `n` give distinct streams.

  Zero is the one state xorshift32 cannot leave (0 xor anything shifted is
  still 0), so it is mapped to a fixed non-zero constant rather than silently
  producing an all-zero stream."
  [n]
  (let [s (u32 #?(:clj (long n) :cljs (js/Math.floor n)))]
    {:s (if (zero? s) 0x9E3779B9 s)}))

(defn- advance
  "One xorshift32 step: `x ^= x<<13; x ^= x>>>17; x ^= x<<5`."
  [{:keys [s]}]
  (let [x (u32 (bit-xor s (u32 (bit-shift-left s 13))))
        x (u32 (bit-xor x (unsigned-bit-shift-right x 17)))
        x (u32 (bit-xor x (u32 (bit-shift-left x 5))))]
    {:s x}))

;; ---------------------------------------------------------------------------
;; draws
;; ---------------------------------------------------------------------------

(defn next-uint
  "Uniform integer in `[0, 2^32)`. Returns `[x state']`."
  [st]
  (let [st' (advance st)]
    [(:s st') st']))

(defn next-double
  "Uniform in `[0, 1)` with 53 bits of resolution. Returns `[x state']`.

  Two 32-bit draws are combined rather than one scaled draw: a single
  xorshift32 word gives only 2^32 distinct values, which shows up as visible
  banding once a mutation sigma is small."
  [st]
  (let [[hi st1] (next-uint st)
        [lo st2] (next-uint st1)]
    ;; 21 high bits + 32 low bits = 53, exactly a double's mantissa
    [(/ (+ (* (unsigned-bit-shift-right hi 11) 4294967296.0) lo)
        9007199254740992.0)
     st2]))

(defn next-signed
  "Uniform in `[-1, 1)`. Returns `[x state']`."
  [st]
  (let [[u st'] (next-double st)]
    [(- (* 2.0 u) 1.0) st']))

(defn next-int
  "Uniform integer in `[0, n)`. Returns `[i state']`. `n` must be positive."
  [st n]
  (let [[u st'] (next-double st)]
    [(min (dec n) (int (* u n))) st']))

(defn gaussian
  "Standard normal via Box-Muller. Returns `[x state']`.

  Consumes two uniforms and discards the second Box-Muller output. Keeping
  the spare would make a draw depend on how many draws preceded it in the
  same state, which breaks the `[value state']` contract that lets an
  out-of-order evaluator reproduce the serial result."
  [st]
  (let [[u1 st1] (next-double st)
        [u2 st2] (next-double st1)
        u1 (max u1 1e-12)
        pi #?(:clj Math/PI :cljs js/Math.PI)
        r  #?(:clj (Math/sqrt (* -2.0 (Math/log u1)))
              :cljs (js/Math.sqrt (* -2.0 (js/Math.log u1))))
        c  #?(:clj (Math/cos (* 2.0 pi u2))
              :cljs (js/Math.cos (* 2.0 pi u2)))]
    [(* r c) st2]))

(defn split
  "Derive an independent child stream. Returns `[child-state state']`.

  Gives each genome its own noise so the order in which genomes are evaluated
  -- serially, in parallel, or resumed after a crash -- cannot change anyone
  else's draws."
  [st]
  (let [[a st1] (next-uint st)
        [b st2] (next-uint st1)]
    [(seed (u32 (bit-xor a (u32 (bit-shift-left b 7))))) st2]))

(defn doubles-n
  "`n` uniform `[0,1)` draws. Returns `[vector state']`."
  [st n]
  (loop [i 0 st st acc []]
    (if (= i n)
      [acc st]
      (let [[x st'] (next-double st)] (recur (inc i) st' (conj acc x))))))

(defn gaussians-n
  "`n` standard-normal draws. Returns `[vector state']`."
  [st n]
  (loop [i 0 st st acc []]
    (if (= i n)
      [acc st]
      (let [[x st'] (gaussian st)] (recur (inc i) st' (conj acc x))))))
