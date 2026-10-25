(ns cartpole-wasm
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-cartpole-wasm Rust crate
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace from kami-engine\") as
  part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Purpose: kami-cartpole-wasm was a JS-callable wasm-bindgen wrapper (`CartpoleHandle`)
  around `kami_shugyo::CartpoleEnv`, demonstrating Phase C of ADR-2605261800 (KAMI canonical
  Rust -> wasm32 -> JS/Isaac-Sim-style RL env). The deleted `src/lib.rs` itself was pure
  wasm-bindgen boundary glue (`#[wasm_bindgen] impl CartpoleHandle { new/reset/step/... }`)
  delegating all cartpole dynamics to the separate `kami_shugyo` crate, whose source is out
  of scope for this restoration. To preserve real computational content (not just glue),
  this namespace ports the classic Barto/Sutton/Anderson cartpole equations of motion — the
  same dynamics `kami_shugyo::CartpoleEnv` implements and that `CartpoleHandle` exposed over
  the wasm boundary — as pure, zero-dependency CLJC data + functions, matching the original
  JS-facing API surface (`reset(seed) -> [x x-dot theta theta-dot]`,
  `step(force) -> [x x-dot theta theta-dot reward terminated? truncated?]`,
  `observation-dim`, `action-dim`, `kami-cartpole-version`) but functional rather than
  `&mut self`-mutating: `step-state` takes and returns an immutable state map. Native
  execution (wgpu / wasmtime / wasmi / actual PhysX/Isaac-Sim bridging) stays substrate;
  this namespace owns the CLJC contracts / pure dynamics / EDN IR for the domain.")

;; ---------------------------------------------------------------------------
;; Physical constants (classic CartPole-v1 parameters; SI units except angle = rad)
;; ---------------------------------------------------------------------------

(def gravity 9.8)
(def masscart 1.0)
(def masspole 0.1)
(def total-mass (+ masscart masspole))
(def pole-half-length 0.5)
(def polemass-length (* masspole pole-half-length))
(def tau
  "Seconds between state updates (fixed simulation step)."
  0.02)
(def theta-threshold-radians
  "12 degrees, expressed in radians -- episode terminates if the pole tips past this."
  (/ (* 12.0 2.0 #?(:clj Math/PI :cljs js/Math.PI)) 360.0))
(def x-threshold
  "Cart position past which the episode terminates."
  2.4)
(def max-episode-steps
  "Step budget after which the episode is truncated (not terminated)."
  500)

(def observation-dim 4)
(def action-dim 1)

(def kami-cartpole-version
  "ADR-2605261800@R1.1")

;; ---------------------------------------------------------------------------
;; Deterministic seeded PRNG (portable LCG; JVM Math and JS doubles agree on
;; this integer arithmetic within double precision for the ranges used here)
;; ---------------------------------------------------------------------------

(def ^:private lcg-modulus 2147483648)
(def ^:private lcg-multiplier 1103515245)
(def ^:private lcg-increment 12345)

(defn lcg-next-seed
  "Advance the LCG seed by one step."
  [seed]
  (mod (+ (* seed lcg-multiplier) lcg-increment) lcg-modulus))

(defn lcg-rand01
  "Returns [value next-seed] where value is uniform in [0, 1)."
  [seed]
  (let [seed' (lcg-next-seed seed)]
    [(/ (double seed') (double lcg-modulus)) seed']))

(defn seeded-uniform-vec
  "Draws n values uniform in [low, high) deterministically from seed.
  Returns [values next-seed]."
  [seed n low high]
  (loop [i 0 s seed acc []]
    (if (= i n)
      [acc s]
      (let [[v s'] (lcg-rand01 s)]
        (recur (inc i) s' (conj acc (+ low (* v (- high low)))))))))

;; ---------------------------------------------------------------------------
;; Pure dynamics (ported from kami_shugyo::CartpoleEnv equations of motion)
;; ---------------------------------------------------------------------------

(defn env-reset
  "`CartpoleHandle::reset(seed)` ported as a pure function.
  Returns a fresh state map with [x x-dot theta theta-dot] each perturbed
  uniformly in [-0.05, 0.05), :steps 0, and the advanced PRNG :seed carried
  forward for reproducibility."
  [seed]
  (let [[[x x-dot theta theta-dot] seed'] (seeded-uniform-vec seed 4 -0.05 0.05)]
    {:x x :x-dot x-dot :theta theta :theta-dot theta-dot
     :steps 0 :seed seed'}))

(defn- terminated?
  [{:keys [x theta]}]
  (or (< x (- x-threshold))
      (> x x-threshold)
      (< theta (- theta-threshold-radians))
      (> theta theta-threshold-radians)))

(defn step-state
  "`CartpoleHandle::step(force)` ported as a pure function: takes the current
  state map and an applied force (Newtons), returns the next state map with
  :reward, :terminated and :truncated set for this transition. This replaces
  the original `&mut self` mutation with an immutable state-in/state-out fn."
  [{:keys [x x-dot theta theta-dot steps] :as state} force]
  (let [costheta (#?(:clj Math/cos :cljs js/Math.cos) theta)
        sintheta (#?(:clj Math/sin :cljs js/Math.sin) theta)
        temp (/ (+ force (* polemass-length theta-dot theta-dot sintheta))
                total-mass)
        thetaacc (/ (- (* gravity sintheta) (* costheta temp))
                    (* pole-half-length
                       (- (/ 4.0 3.0)
                          (/ (* masspole costheta costheta) total-mass))))
        xacc (- temp (/ (* polemass-length thetaacc costheta) total-mass))
        x' (+ x (* tau x-dot))
        x-dot' (+ x-dot (* tau xacc))
        theta' (+ theta (* tau theta-dot))
        theta-dot' (+ theta-dot (* tau thetaacc))
        steps' (inc steps)
        next-state (assoc state
                           :x x' :x-dot x-dot' :theta theta' :theta-dot theta-dot'
                           :steps steps')
        done? (terminated? next-state)
        truncated? (and (not done?) (>= steps' max-episode-steps))]
    (assoc next-state
           :reward 1.0
           :terminated done?
           :truncated truncated?)))

;; ---------------------------------------------------------------------------
;; wasm-bindgen-API-shaped adapters (flattened numeric vectors, matching the
;; original `Vec<f32>` JS-facing surface of `CartpoleHandle`)
;; ---------------------------------------------------------------------------

(defn state->reset-vec
  "Flattens a state map to the 4-tuple `reset` returned over the wasm
  boundary: [x x-dot theta theta-dot]."
  [{:keys [x x-dot theta theta-dot]}]
  [x x-dot theta theta-dot])

(defn state->step-vec
  "Flattens a state map (post step-state) to the 7-tuple `step` returned over
  the wasm boundary: [x x-dot theta theta-dot reward terminated? truncated?]
  with booleans coerced to 1.0/0.0 as the original Rust did."
  [{:keys [x x-dot theta theta-dot reward terminated truncated]}]
  [x x-dot theta theta-dot reward (if terminated 1.0 0.0) (if truncated 1.0 0.0)])

(defn cartpole-reset
  "`cartpole.reset(seed)` -> flattened 4-tuple, plus the full state map (the
  caller keeps the state map to pass into `cartpole-step`)."
  [seed]
  (let [state (env-reset seed)]
    {:obs (state->reset-vec state) :state state}))

(defn cartpole-step
  "`cartpole.step(state, force)` -> flattened 7-tuple, plus the full next
  state map."
  [state force]
  (let [state' (step-state state force)]
    {:obs (state->step-vec state') :state state'}))
