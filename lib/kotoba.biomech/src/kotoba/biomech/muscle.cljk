(ns kotoba.biomech.muscle
  "1-D lumped mass-spring-damper muscle model with an active contractile
  element (Hill-type reduced to linear). Zero-dep, pure .cljc.

  The muscle is a single point mass attached to a fixed origin by a
  parallel passive element (spring + damper, rest length L0) and an
  active contractile element that pulls toward the origin (shortening),
  scaled by activation, force-length, and force-velocity relationships.
  The passive element has two models — a linear bidirectional spring
  (default) and the tension-only exponential the musculoskeletal literature
  specifies. `passive-force` states which is which and why the default is
  the one that is not the literature's.
  The muscle-tendon path adds first-order excitation/activation dynamics and
  a tension-only series-elastic tendon; the original instantaneous-activation
  `step` API remains available for compatibility.

  Sign convention: :length is the mass position along the muscle axis
  measured from the origin [m]; positive = stretched beyond rest length.
  The restoring spring force, damping, and active contractile pull all
  act in the negative direction (toward the origin / shortening) when the
  muscle is stretched and/or activating.

  `step` advances state by semi-implicit Euler with sub-stepping for
  stability. This is a *lumped* teaching/prototyping model, not a FEM
  muscle. Phase 2 routes large-scale soft-tissue deformation through
  kotoba-lang/kami-vehicle's XPBD mass-spring solver instead.")

(def default-params
  "Representative lumped params for an adult skeletal-muscle belly:
  mass ~300 g, rest length ~15 cm, peak isometric force ~1 kN.
  Numbers are order-of-magnitude teaching defaults, not patient-specific.

  CORRECTED 2026-09-07. This docstring used to claim the passive stiffness was
  \"tuned so a +30% stretch gives ~40 N passive restoring force\". Measured by
  running `acceleration` at L = 1.30 * L0 with zero velocity and zero
  activation, it gives **9.0 N** (200 N/m * 0.045 m) — the claim was 4.4x the
  behaviour of the parameter next to it. Nothing tested the sentence, so it
  survived. The parameter is left alone and the sentence is corrected: retuning
  k to make the old prose true would have changed every passive number in this
  repo to rescue a comment.

  The passive element here is a LINEAR, BIDIRECTIONAL spring about rest-length:
  it resists compression below L0 as well as stretch above it. That is a lumped
  mass-spring choice, not a claim about muscle tissue — real passive muscle
  tension is tension-only and stiffens exponentially. `cloud-itonami/suji`
  models the latter; see the boundary section of this repo's README for the
  measured divergence between the two."
  {:mass 0.3
   :passive-stiffness 200.0        ; N/m, read by :linear-bidirectional only
   :damping 5.0                    ; N·s/m
   ;; Passive parallel element. `:linear-bidirectional` (the default, and the
   ;; only behaviour this namespace had before 2026-09-07) or `:thelen-2003`.
   ;; `passive-force` carries the decision; `passive-force-length-multiplier`
   ;; carries the sourcing for the two constants below.
   :passive-model :linear-bidirectional
   :passive-strain-at-max-force 0.6 ; ε₀^M — Thelen (2003) young adult
   :passive-shape-factor 5.0        ; k^PE — Thelen (2003)
   :active-max-force 1000.0        ; N
   :rest-length 0.15               ; m
   :optimal-length 0.15            ; m, peak of the active force-length curve
   :max-shortening-velocity 1.0     ; m/s, |v| at which active force -> 0
   :eccentric-max-factor 1.5        ; max active force while lengthening / Fmax
   :activation-time-constant 0.015  ; s, excitation rising response
   :deactivation-time-constant 0.050 ; s, excitation falling response
   :tendon-slack-length 0.20        ; m
   :tendon-stiffness 20000.0})      ; N/m, linear series-elastic element

(defn- clip-activation [a]
  (let [x (double a)] (max 0.0 (min 1.0 x))))

(defn make-state
  "Initial muscle state. length [m], velocity [m/s], activation [0,1]."
  ([length] (make-state length 0.0 0.0))
  ([length velocity]
   (make-state length velocity 0.0))
  ([length velocity activation]
   {:length (double length)
    :velocity (double velocity)
    :activation (clip-activation activation)}))

(defn make-params
  "Params map; overrides (keyword or string keys) merge onto default-params."
  ([] default-params)
  ([overrides] (merge default-params (update-keys overrides keyword))))

(defn force-length-factor
  "Hill-type active force-length scaling: the active contractile force peaks
  at the muscle's optimal length and falls off as a parabola outside the
  physiological range. Returns a multiplier in [0, 1] — 1.0 at length =
  optimal-length, ~0 outside [0.5, 1.5] * optimal-length."
  [length optimal-length]
  (let [ratio (/ (double length) (double optimal-length))]
    (max 0.0 (- 1.0 (* 4.0 (- ratio 1.0) (- ratio 1.0))))))

(defn passive-force-length-multiplier
  "Normalized passive (parallel-elastic) force at `length`, as a fraction of
  maximum isometric force. Tension-only: exactly 0 at and below
  `optimal-length`, rising exponentially above it.

  This is Thelen (2003) Eq. (3), quoted from the paper:

      F̄^PE = (e^(k^PE (L̄^M − 1) / ε₀^M) − 1) / (e^(k^PE) − 1)

  where F̄^PE is normalized passive muscle force, k^PE is an exponential shape
  factor and ε₀^M is \"the passive muscle strain due to maximum isometric
  force\". Thelen sets k^PE = 5 and ε₀^M = 0.60 for young adults, reduced to
  0.50 for older adults to represent the age-related increase in passive
  stiffness (Thelen 2003, Table 1, p. 71).
    Thelen, D.G. (2003) Adjustment of muscle mechanics model parameters to
    simulate dynamic contractions in older adults. ASME Journal of
    Biomechanical Engineering 125(1):70-77. DOI 10.1115/1.1531112.

  THE CLAMP IS NOT IN THE PAPER'S EQUATION, AND IS NOT OPTIONAL. Eq. (3) as
  printed is negative for L̄^M < 1: the numerator e^(negative) − 1 is below
  zero, so the bare formula makes passive tissue PUSH when shortened. Every
  shipped implementation of it clamps. OpenSim's does so by construction
  (OpenSim/Actuators/Thelen2003Muscle.cpp, read 2026-09-07):

      double fpe = 0;
      ...
      if(lceN > 1.0){ ... fpe = (t5 - 0.10e1) / (t7 - 0.10e1); }
      return fpe;

  with defaults `constructProperty_FmaxMuscleStrain(0.6)` and
  `constructProperty_KshapePassive(5.0)` — the same two numbers as the paper.
  Defaults here match OpenSim's, so this function reproduces the curve the
  musculoskeletal-simulation literature actually runs.

  `params` supplies `:optimal-length` (falling back to `:rest-length`),
  `:passive-strain-at-max-force` (ε₀^M) and `:passive-shape-factor` (k^PE).
  At length = (1 + ε₀^M) * optimal the result is exactly 1.0, which is what
  ε₀^M means."
  [length {:keys [optimal-length rest-length
                  passive-strain-at-max-force passive-shape-factor]}]
  (let [opt  (double (or optimal-length rest-length))
        e0   (double (or passive-strain-at-max-force 0.6))
        kpe  (double (or passive-shape-factor 5.0))]
    (when-not (pos? opt)
      (throw (ex-info "optimal length must be positive" {:optimal-length opt})))
    (when-not (pos? e0)
      (throw (ex-info "passive strain at max force must be positive"
                      {:passive-strain-at-max-force e0})))
    (let [ratio (/ (double length) opt)]
      (if (<= ratio 1.0)
        0.0
        (/ (- (Math/exp (* kpe (/ (- ratio 1.0) e0))) 1.0)
           (- (Math/exp kpe) 1.0))))))

(defn passive-force
  "Tension [N] carried by the parallel elastic element at `length`. Positive =
  pulling the mass back toward the origin. Selected by `:passive-model`.

  `:linear-bidirectional` (DEFAULT) — k*(L − L0). Resists compression below L0
  as well as stretch above it, so it returns a NEGATIVE value (a push) when
  shortened. `:thelen-2003` — `passive-force-length-multiplier` scaled by
  `:active-max-force`; never negative.

  WHY THE DEFAULT IS THE ONE THAT IS NOT THE LITERATURE'S. Settled 2026-09-07
  against five sources that could be read and one recorded as unobtainable
  (Zajac 1989); the full provenance is in this repo's README, and nothing is
  cited here that was not read. Every readable one of them specifies passive
  force as tension-only with an onset at or near optimal length, and the one
  physiology paper among them states it directly — \"Passive tension is borne
  by a muscle when it is lengthened beyond slack length\" (Ward et al. 2020,
  Frontiers in Physiology 11:211). On the tissue question there is no
  disagreement to settle: a muscle belly does not push.

  The bidirectional branch survives because — measured — it is not modelling
  tissue at all: it is the only static equilibrium the tendon-free `step` path
  has below rest length. Measured 2026-09-07, holding everything else fixed and
  running `simulate` for 0.5 s at activation 1.0 from L0:

    :linear-bidirectional  settles at L/L0 = 0.5037, and it is a real force
                           balance: spring +14.89 N against active −14.74 N
    tension-only           coasts to L/L0 = 0.1287 and stops there only
                           because the active force-length parabola is zero
                           below 0.5*L0 and damping ran the velocity out —
                           a length set by integration history, not by forces

  A muscle belly compressed to 13% of rest length is not a better answer than
  a spring that pushes; it is the same error with no equilibrium. What
  actually holds a muscle out in the body is its load, and this repo has that:
  in `step-muscle-tendon` the series tendon supplies it, and there the choice
  BARELY MATTERS — same protocol, fixed MTU length, the two models settle at
  L/L0 = 0.7927 and 0.7914, a difference of 0.17%, because at that length the
  tendon carries 822 N against the passive element's 6.2 N (and 826 N against
  the tension-only element's 0).

  So: `:linear-bidirectional` is a numerical boundary for the tendon-free
  lumped path and is documented as such, not as a claim about tissue.
  `:thelen-2003` is the tissue model. If you are modelling passive muscle
  ANYWHERE THAT PASSIVE FORCE IS THE ANSWER — flexion-relaxation, a stretched
  antagonist, %MVC bookkeeping — select `:thelen-2003`; the default understates
  it by 8.4x at +30% stretch (9.0 N against 75.9 N) and has the wrong sign
  below L0.
  Prefer `step-muscle-tendon` with `:thelen-2003` over the bare `step` path:
  that combination is both the literature's curve and a bounded model."
  [length {:keys [passive-model passive-stiffness rest-length active-max-force]
           :as params}]
  (case (or passive-model :linear-bidirectional)
    :linear-bidirectional
    (* (double passive-stiffness) (- (double length) (double rest-length)))

    :thelen-2003
    (* (double active-max-force) (passive-force-length-multiplier length params))

    (throw (ex-info "unknown :passive-model" {:passive-model passive-model}))))

(defn force-velocity-factor
  "Hill force-velocity (concentric): active force falls linearly toward 0 as
  shortening velocity grows, reaching 0 at v = -v-max. During eccentric
  contraction (lengthening, v > 0), force rises linearly from the isometric
  value to `eccentric-max-factor` at v-max and remains capped there. v is
  muscle length velocity [m/s] (negative = shortening)."
  ([v v-max]
   (force-velocity-factor v v-max 1.5))
  ([v v-max eccentric-max-factor]
   (let [v (double v)
         vmax (double v-max)
         eccentric-max (max 1.0 (double eccentric-max-factor))]
     (when-not (pos? vmax)
       (throw (ex-info "v-max must be positive" {:v-max v-max})))
    (if (neg? v)
      (max 0.0 (/ (+ vmax v) vmax))   ; 1 at v=0, 0 at v=-vmax
      (min eccentric-max
           (+ 1.0 (* (- eccentric-max 1.0) (/ v vmax))))))))

(defn activation-step
  "Advance neural activation toward excitation over dt [s]. Rising and
  falling responses use separate time constants and an exact exponential
  update, so the result remains in [0,1] for any non-negative dt."
  [activation excitation
   {:keys [activation-time-constant deactivation-time-constant]}
   dt]
  (let [a (clip-activation activation)
        e (clip-activation excitation)
        tau (double (if (> e a)
                      (or activation-time-constant 0.015)
                      (or deactivation-time-constant 0.050)))
        dt (double dt)]
    (when-not (pos? tau)
      (throw (ex-info "activation time constant must be positive" {:tau tau})))
    (when (neg? dt)
      (throw (ex-info "dt must be non-negative" {:dt dt})))
    (clip-activation (+ e (* (- a e) (Math/exp (/ (- dt) tau)))))))

(defn tendon-force
  "Tensile force [N] in a linear series-elastic tendon. `mtu-length` is the
  total muscle-tendon-unit length; the contractile-element length comes from
  state. Tendon is tension-only and produces zero force below slack length."
  [{:keys [length]}
   {:keys [tendon-slack-length tendon-stiffness]}
   mtu-length]
  (let [slack (double (or tendon-slack-length 0.20))
        stiffness (double (or tendon-stiffness 20000.0))
        extension (- (double mtu-length) (double length) slack)]
    (when (neg? stiffness)
      (throw (ex-info "tendon stiffness must be non-negative"
                      {:tendon-stiffness stiffness})))
    (* stiffness (max 0.0 extension))))

(defn acceleration
  "Acceleration [m/s^2] of the mass given state, params, activation (0..1).

  m*a = -f_passive(L)            ; parallel elastic element, `passive-force`
        - c*v                    ; viscous damping (opposes velocity)
        - act*fl(L)*Fmax         ; active contractile pull (toward origin),
                                 ; scaled by Hill force-length factor fl

  i.e. for a stretched (L > L0), outward-moving (v > 0), activating
  muscle, all three force contributions are negative — sign kept explicit
  so the physics reads.

  The first term used to be written here as `-k*(L - L0)`. It is now delegated
  to `passive-force`, which carries both models and the reason the default is
  the linear bidirectional spring rather than the literature's tension-only
  curve. Under the default this line computes exactly what it always did."
  [{:keys [length velocity]}
   {:keys [mass damping active-max-force rest-length optimal-length
           max-shortening-velocity eccentric-max-factor]
    :as params}
   activation]
  (let [opt       (or optimal-length rest-length)
        vmax      (or max-shortening-velocity 1.0)
        f-spring  (* -1.0 (passive-force length params))
        f-damper  (* -1.0 damping velocity)
        fl        (force-length-factor length opt)
        fv        (force-velocity-factor velocity vmax (or eccentric-max-factor 1.5))
        f-active  (* -1.0 (clip-activation activation) fl fv active-max-force)]
    (/ (+ f-spring f-damper f-active) mass)))

(defn muscle-tendon-acceleration
  "Contractile-element acceleration [m/s^2] in a fixed-length muscle-tendon
  unit. Active/passive muscle force pulls toward shortening; the series
  tendon pulls toward lengthening. State activation, rather than instantaneous
  excitation, drives the active force."
  [state params mtu-length]
  (+ (acceleration state params (or (:activation state) 0.0))
     (/ (tendon-force state params mtu-length) (:mass params))))

(defn step
  "Advance muscle state by dt [s] under activation (0..1). Semi-implicit
  Euler with substeps (default 8) for numerical stability."
  ([state params activation dt]
   (step state params activation dt 8))
  ([state params activation dt substeps]
   (let [n   (max 1 (int substeps))
         sdt (/ (double dt) n)]
     (loop [i 0 st state]
       (if (>= i n)
         st
         (let [{:keys [velocity]} st
               a     (acceleration st params activation)
               v-new (+ velocity (* a sdt))
               l-new (+ (:length st) (* v-new sdt))]
           (recur (inc i) (assoc st :length l-new :velocity v-new))))))))

(defn step-muscle-tendon
  "Advance a Hill-type muscle-tendon unit by dt [s] under neural excitation.
  Activation dynamics and series-elastic tendon force are integrated within
  each substep. `mtu-length` is held fixed during this step."
  ([state params excitation mtu-length dt]
   (step-muscle-tendon state params excitation mtu-length dt 8))
  ([state params excitation mtu-length dt substeps]
   (let [n (max 1 (int substeps))
         sdt (/ (double dt) n)]
     (loop [i 0 st state]
       (if (>= i n)
         st
         (let [a-new (activation-step (or (:activation st) 0.0)
                                      excitation params sdt)
               active-state (assoc st :activation a-new)
               a (muscle-tendon-acceleration active-state params mtu-length)
               v-new (+ (:velocity st) (* a sdt))
               l-new (+ (:length st) (* v-new sdt))]
           (recur (inc i) (assoc active-state
                                 :length l-new
                                 :velocity v-new))))))))

(defn simulate-muscle-tendon
  "Run n fixed-length muscle-tendon-unit steps; returns successor states."
  [init params excitation mtu-length dt n]
  (loop [i 0 st init acc []]
    (if (>= i n)
      acc
      (let [next (step-muscle-tendon st params excitation mtu-length dt)]
        (recur (inc i) next (conj acc next))))))

(defn simulate
  "Run n steps of size dt from init under constant activation. Returns a
  vector of n successor states (init itself is NOT included — the caller
  already holds it)."
  [init params activation dt n]
  (loop [i 0 st init acc []]
    (if (>= i n)
      acc
      (let [next (step st params activation dt)]
        (recur (inc i) next (conj acc next))))))
