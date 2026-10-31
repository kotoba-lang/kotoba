(ns vehicle.beam
  "Beam -- pairwise spring-damper between two nodes.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   A beam reproduces BeamNG semantics:
     F = -k * (L - L0_eff) - d * (dL/dt)

   where `L0_eff` is the *effective* rest length (drifts under plastic
   deformation) and `k`, `d` are the spring stiffness and damping. Beams may
   be `:normal` (always active), `:bounded` (active only between min/max
   ratio), `:hydro` (length is a function of an external control like
   steering), `:pressured` (rest length increases with internal pressure --
   used for tire sidewalls), or `:support` (compression-only, e.g. bump-stop).

   Plastic deformation: when |strain| exceeds `:deform-limit`, `L0_eff`
   follows the current length (yielding). When the strain exceeds
   `:break-limit`, the beam snaps and is removed from the integration.")

;; beam-type is a map {:kind :normal|:bounded|:hydro|:pressured|:support ...}
(def beam-type-normal {:kind :normal})
(def beam-type-support {:kind :support})
(defn beam-type-bounded [min-ratio max-ratio] {:kind :bounded :min-ratio min-ratio :max-ratio max-ratio})
(defn beam-type-hydro [factor extension] {:kind :hydro :factor factor :extension extension})
(defn beam-type-pressured [pressure-factor reference-pressure]
  {:kind :pressured :pressure-factor pressure-factor :reference-pressure reference-pressure})

(def default-deform-params
  {:deform-limit 0.10 :break-limit 0.45 :max-plastic-strain 0.40})

(defn new-beam [id n1 n2 rest-length spring damping]
  {:id id
   :n1 n1
   :n2 n2
   :rest-length rest-length
   :effective-length rest-length
   :spring spring
   :damping damping
   :beam-type beam-type-normal
   :deform default-deform-params
   :break-group nil
   :broken false
   :plastic-strain 0.0
   :current-length rest-length})

(defn with-type [beam t] (assoc beam :beam-type t))
(defn with-deform [beam d] (assoc beam :deform d))
(defn with-break-group [beam g] (assoc beam :break-group g))

(defn live-rest-length [beam pressure]
  (let [bt (:beam-type beam)]
    (case (:kind bt)
      :hydro (* (:effective-length beam) (+ 1.0 (* (:factor bt) (:extension bt))))
      :pressured (* (:effective-length beam)
                     (+ 1.0 (* (:pressure-factor bt) (- pressure (:reference-pressure bt)))))
      (:effective-length beam))))

(defn force-scalar
  "Evaluate the spring scalar force in newtons (positive = pushing nodes
   apart, negative = pulling them together)."
  [beam current-length rate pressure]
  (if (:broken beam)
    0.0
    (let [l0 (max (live-rest-length beam pressure) 1e-6)
          strain (/ (- current-length l0) l0)
          bt (:beam-type beam)
          spring (:spring beam)
          damping (:damping beam)]
      (case (:kind bt)
        :bounded
        ;; Slack inside [min-ratio, max-ratio]; past either edge the beam
        ;; acts like a spring pulling/pushing back toward that edge (not
        ;; toward l0), so force must rise continuously from 0.0 at the
        ;; boundary -- matching vehicle.cljc's XPBD fast path, which
        ;; targets (* rest ratio) rather than l0 itself.
        (let [ratio (/ current-length l0)]
          (cond
            (< ratio (:min-ratio bt))
            (- (- (* spring (- current-length (* l0 (:min-ratio bt))))) (* damping rate))
            (> ratio (:max-ratio bt))
            (- (- (* spring (- current-length (* l0 (:max-ratio bt))))) (* damping rate))
            :else 0.0))
        :support
        (if (< current-length l0)
          (- (- (* spring (- current-length l0))) (* damping rate))
          0.0)
        (- (- (* spring strain l0)) (* damping rate))))))

(defn- copysign [mag sign]
  (if (neg? sign) (- (Math/abs mag)) (Math/abs mag)))

(defn update-plastic
  "Update plastic deformation and break state given the current geometric
   length. Returns `[beam' broke?]`."
  [beam current-length]
  (if (:broken beam)
    [beam false]
    (let [beam (assoc beam :current-length current-length)
          l0 (max (:effective-length beam) 1e-6)
          strain (/ (- current-length l0) l0)
          abs-strain (Math/abs strain)
          deform (:deform beam)]
      (cond
        (>= abs-strain (:break-limit deform))
        [(assoc beam :broken true) true]

        (> abs-strain (:deform-limit deform))
        (let [excess (- abs-strain (:deform-limit deform))
              yield-step (* (copysign excess strain) 0.5)
              new-strain (+ (:plastic-strain beam) (Math/abs yield-step))]
          (if (<= new-strain (:max-plastic-strain deform))
            [(assoc beam
                     :plastic-strain new-strain
                     :effective-length (max (* l0 (+ 1.0 yield-step)) 1e-3))
             false]
            [beam false]))

        :else [beam false]))))
