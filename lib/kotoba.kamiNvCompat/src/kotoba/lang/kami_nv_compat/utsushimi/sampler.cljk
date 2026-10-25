(ns kotoba.lang.kami-nv-compat.utsushimi.sampler
  "utsushimi — clean-room synthetic-data sampler (Replicator DR core).
  Portable .cljc port of src/utsushimi/sampler.ts. Wave 31.

  The canonical KAMI implementation behind nv-compat/omni-replicator-core.
  NVIDIA Omniverse Replicator drives domain-randomization from seedable
  distributions; this module reproduces the documented DR primitives plus
  a 64-bit LCG sampler intended to be BIT-IDENTICAL to the Python
  reference (kotodama.nv_compat.omni.replicator.core._Sampler), so a
  randomization seed produces the same stream in every language — the
  cross-language reproducibility the Replicator G5 gate requires. This
  port has NOT been independently verified against the Python oracle
  (no Python runtime in this environment); it faithfully translates the
  TS reference's formula, and its own internal determinism is tested.

  The LCG is the PCG/Knuth multiplier (6364136223846793005) + increment
  (1442695040888963407) modulo 2^64, needing arbitrary-precision
  arithmetic (state * mul routinely exceeds 64 bits) — like every
  content-addressing/bignum module in this ecosystem (see
  multiformats.core), the real implementation is :clj (data-generation
  pipelines run build/server-side, not in the browser); the :cljs branch
  exposes the same public API as throwing stubs so a .cljc consumer
  compiles cleanly under ClojureScript and fails loudly if it ever tries
  to sample in the browser.

  Clean-room: from-spec PRNG + textbook distributions. No Replicator
  source or binaries. ADR-2605261800 SD6 / D10.4 utsushimi.")

#?(:clj
(do

(def ^:private two64 18446744073709551616)
(def ^:private two33 8589934592)
(def ^:private two31 2147483648)
(def ^:private lcg-mul 6364136223846793005)
(def ^:private lcg-inc 1442695040888963407)

(defn make-sampler
  "A new, seedable 64-bit LCG sampler (an atom holding the 64-bit state)."
  ([] (make-sampler 0))
  ([seed]
   (atom (mod (+' (*' (bigint seed) lcg-mul) lcg-inc) two64))))

(defn next-u01!
  "Next uniform in [0, 1) — ((state>>33) & 0x7FFFFFFF) / 2^31."
  [sampler]
  (swap! sampler (fn [state] (mod (+' (*' state lcg-mul) lcg-inc) two64)))
  (let [top (mod (quot @sampler two33) two31)]
    (/ (double top) (double two31))))

(defn next-uniform!
  [sampler low high]
  (+ low (* (- high low) (next-u01! sampler))))

(defn next-normal!
  "Box-Muller normal (consumes two uniforms, matching the reference)."
  [sampler mean std]
  (let [u1 (max (next-u01! sampler) 1e-12)
        u2 (next-u01! sampler)
        z (* (Math/sqrt (* -2.0 (Math/log u1))) (Math/cos (* 2.0 Math/PI u2)))]
    (+ mean (* std z))))

(defn next-truncated-normal!
  "Rejection-sampled truncated normal (caps at 20 attempts like the ref)."
  [sampler mean std low high]
  (loop [i 0]
    (if (>= i 20)
      (max low (min high mean))
      (let [v (next-normal! sampler mean std)]
        (if (and (>= v low) (<= v high))
          v
          (recur (inc i)))))))

;; ── module-level shared sampler (rep.distribution.sample default) ───────

(def ^:private global-sampler-atom (atom (make-sampler 0)))

(defn seed-global!
  "Re-seed the module-level sampler used by `sample` with no explicit
  sampler (mirrors seed_global)."
  [seed]
  (reset! global-sampler-atom (make-sampler seed)))

(defn global-sampler
  []
  @global-sampler-atom)

)) ;; end #?(:clj (do …))

#?(:cljs
(do

(defn- nope [n] (throw (ex-info (str "utsushimi.sampler/" n " is :clj-only "
                                      "(DR sampling runs build/server-side, not in cljs)") {})))
(defn make-sampler [& _] (nope "make-sampler"))
(defn next-u01! [& _] (nope "next-u01!"))
(defn next-uniform! [& _] (nope "next-uniform!"))
(defn next-normal! [& _] (nope "next-normal!"))
(defn next-truncated-normal! [& _] (nope "next-truncated-normal!"))
(defn seed-global! [& _] (nope "seed-global!"))
(defn global-sampler [& _] (nope "global-sampler"))

))
