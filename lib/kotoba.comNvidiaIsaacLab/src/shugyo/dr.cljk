(ns shugyo.dr
  "Per-env domain randomisation for the Cartpole env(s) — 1:1 port of the
  original crate's `dr.rs`.

  Mirrors the sim2real workflow that Isaac Lab / Replicator users follow: each
  parallel env gets a slightly different physics config so the trained policy
  generalises across the real-world parameter distribution.

  Each randomisable field has a `(low, high)` range; `dr-sample` draws
  per-env values from a uniform LCG sampler (`shugyo.lcg`, same constants as
  the original `kami_genesis::cartpole_env::Lcg`).

  Duck-typing note: the original `dr.rs` imported `kami_genesis::CartpoleConfig`
  — a plain data struct whose *shape* never actually depended on kami-genesis
  physics code, only its *definition site*. Since kami-genesis was never
  restored as a kotoba-lang repo, this port duck-types `CartpoleConfig` locally
  as a plain map with the same fields (`cart-mass`, `pole-mass`,
  `pole-half-length`, `gravity`, `force-mag`, `dt`) — see `cartpole-config` and
  `shugyo.cartpole`, which is the sole consumer of this shape."
  (:require [shugyo.lcg :as lcg]))

;; ---------------------------------------------------------------------------
;; Duck-typed CartpoleConfig (see docstring above)
;; ---------------------------------------------------------------------------

(defn cartpole-config
  "Construct a CartpoleConfig map. All fields required; this is a plain data
  constructor, not a physics object — see `shugyo.cartpole` for the ODE that
  consumes it."
  [{:keys [cart-mass pole-mass pole-half-length gravity force-mag dt]}]
  {:cart-mass cart-mass
   :pole-mass pole-mass
   :pole-half-length pole-half-length
   :gravity gravity
   :force-mag force-mag
   :dt dt})

;; ---------------------------------------------------------------------------
;; Range
;; ---------------------------------------------------------------------------

(defn range-new
  "Inclusive `(low, high)` pair. `dr-sample` draws `low + (high-low)*u01()`."
  [low high]
  {:low low :high high})

(defn range-fixed
  "Constant value (low == high): no randomisation."
  [v]
  {:low v :high v})

;; ---------------------------------------------------------------------------
;; DomainRandomizationCfg
;; ---------------------------------------------------------------------------

(defn dr-around
  "Default sim2real ranges around `base`: ±20% mass, ±5% length, ±5% gravity,
  fixed force-mag and dt."
  [base]
  {:cart-mass (range-new (* (:cart-mass base) 0.8) (* (:cart-mass base) 1.2))
   :pole-mass (range-new (* (:pole-mass base) 0.8) (* (:pole-mass base) 1.2))
   :pole-half-length (range-new (* (:pole-half-length base) 0.95) (* (:pole-half-length base) 1.05))
   :gravity (range-new (* (:gravity base) 0.95) (* (:gravity base) 1.05))
   :force-mag (range-fixed (:force-mag base))
   :dt (range-fixed (:dt base))})

(defn dr-identity
  "No randomisation at all — every env gets `base` exactly."
  [base]
  {:cart-mass (range-fixed (:cart-mass base))
   :pole-mass (range-fixed (:pole-mass base))
   :pole-half-length (range-fixed (:pole-half-length base))
   :gravity (range-fixed (:gravity base))
   :force-mag (range-fixed (:force-mag base))
   :dt (range-fixed (:dt base))})

(defn dr-sample
  "Sample one CartpoleConfig from the DR distribution `cfg` using `seed`."
  [cfg base seed]
  (let [state (lcg/lcg-new seed)
        [cart-mass s1] (lcg/next-uniform state (:low (:cart-mass cfg)) (:high (:cart-mass cfg)))
        [pole-mass s2] (lcg/next-uniform s1 (:low (:pole-mass cfg)) (:high (:pole-mass cfg)))
        [pole-half-length s3] (lcg/next-uniform s2 (:low (:pole-half-length cfg)) (:high (:pole-half-length cfg)))
        [gravity s4] (lcg/next-uniform s3 (:low (:gravity cfg)) (:high (:gravity cfg)))
        [force-mag s5] (lcg/next-uniform s4 (:low (:force-mag cfg)) (:high (:force-mag cfg)))
        [dt _s6] (lcg/next-uniform s5 (:low (:dt cfg)) (:high (:dt cfg)))]
    {:cart-mass cart-mass
     :pole-mass pole-mass
     :pole-half-length pole-half-length
     :gravity gravity
     :force-mag force-mag
     :dt dt}))

(defn dr-sample-n
  "Produce `n` per-env configs from the DR distribution `cfg`, seeded
  reproducibly from `base-seed`."
  [cfg base n base-seed]
  (mapv #(dr-sample cfg base (+ base-seed %)) (range n)))
