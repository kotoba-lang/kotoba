(ns cae.h2-line-drop
  "H2 delivery-line steady pressure drop and delivery-pressure feasibility
  (Darcy-Weisbach screening, :h2-line-drop).

  System context: the magnesium-hydrogen-PEMFC electric-drive boundary
  (scripts/hermes-magnesium-systems-bots/system-scope.edn on origin/main)
  names a `:controlled-hydrogen-reactor`, a replaceable Mg/MgH2 cartridge
  and a `:pem-fuel-cell`. The design-domain `:fluid-pressure-and-leak-cae`
  is served upstream by inventory (`:h2-tank-storage`), equilibrium
  (`:h2-desorption`, van't Hoff plateau), kinetics, and heat contracts —
  but NONE of them answers the transport question in between: *after the
  line between bed and fuel-cell inlet, is the pressure still above what
  the fuel cell requires?* A plateau pressure that clears equilibrium
  does not clear plumbing; the delivered pressure at the cell inlet is
  the feasibility quantity for the demand schedule the vehicle plane
  emits. This contract is that smallest transport step.

  Genericity / provenance discipline (mirrors `cae.h2-heat-demand` and
  `cae.h2-tank-storage`):
  - EVERY physical input is caller-supplied with a mandatory non-blank
    `:line-source` provenance string covering the line geometry and the
    Darcy friction factor: `:length-m`, `:diameter-m`, `:friction-factor`
    (Darcy f, dimensionless — NOT the Fanning factor; the caller's
    provenance string must say which correlation it came from), and the
    gas density `:density-kg-m3` at the line state (caller-supplied so no
    ideal-gas or real-gas assumption is baked in here; a caller may feed
    the density implied by a `:h2-tank-storage` result at the same P/T).
  - `:mass-flow-kg-s` is the demanded H2 rate (e.g. a per-interval
    fuel-cell demand from the vehicle plane's consumption profile).
  - `:upstream-pressure-Pa` is the ABSOLUTE supply pressure at the line
    inlet (a `:h2-desorption` equilibrium plateau or a measured tank
    state — caller provenance, not re-derived here).
  - `:min-delivery-pressure-Pa` — the fuel-cell inlet requirement
    (caller-supplied with the same provenance string; fail-closed
    without it). No fuel-cell pressure constant is baked in.

  Model (steady, incompressible screening at the caller's density):
      v   [m/s]  = m-dot / (rho · A),  A = pi · D² / 4
      dP  [Pa]   = f · (L/D) · rho · v² / 2
      p-out [Pa] = p-in − dP
      feasible?  = p-out ≥ p-min
      shortfall-pressure-Pa = max(0, p-min − p-out)   (REPORTED, never
                              thrown — the deficit discipline the H2
                              supply contracts already use)
  The ONLY number this contract supplies is π (mathematics). Every
  result carries the explicit unmeasured envelope (compressibility
  along the line, fittings/bends minor losses, entrance/exit losses,
  two-phase or Joule–Thomson effects, leak rate, transient startup).

  Refusals (fail closed): non-positive/non-finite geometry, flow,
  density, pressures; friction factor outside (0, 1]; blank or missing
  `:line-source`; delivery minimum above the upstream pressure reported
  as infeasible rather than refused (it is a physically expressible,
  measurable state — not a malformed one)."
  (:require [cae.solver :as cae.solver]))

(def ^:private pi Math/PI)

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive! [input ks]
  (doseq [k ks]
    (when-not (and (finite-number? (get input k)) (pos? (double (get input k))))
      (throw (ex-info "h2-line-drop input must be a finite positive number"
                      {:field k :value (get input k)})))))

(defn- nonblank-string! [input k]
  (let [v (get input k)]
    (when-not (and (string? v) (re-find #"\S" v))
      (throw (ex-info "h2-line-drop input must be a non-blank string"
                      {:field k :value v})))))

(defn h2-line-drop
  "Steady Darcy-Weisbach pressure drop of the H2 delivery line and the
  delivery-pressure feasibility at the fuel-cell inlet.

  Case keys:
  - `:mass-flow-kg-s` — demanded H2 mass flow through the line (required,
    positive). Typically a per-interval fuel-cell demand from the
    vehicle plane's consumption profile.
  - `:upstream-pressure-Pa` — ABSOLUTE pressure at the line inlet
    (required, positive; e.g. the `:h2-desorption` equilibrium plateau
    pressure or a measured tank state, caller-provenanced).
  - `:min-delivery-pressure-Pa` — required ABSOLUTE pressure at the
    fuel-cell inlet (required, positive).
  - `:length-m` / `:diameter-m` — line length and inner diameter
    (required, positive).
  - `:friction-factor` — Darcy friction factor f (required, dimensionless,
    in (0, 1]; caller-supplied — this contract invents no correlation).
  - `:density-kg-m3` — H2 density at the line state (required, positive;
    caller-supplied so no gas model is baked in).
  - `:line-source` — non-blank provenance string covering the line
    geometry, the friction-factor correlation and its f-vs-Fanning
    convention, and the density state (required; fail-closed without it).

  Returns a `:screening-only` result with `:velocity-m-s`, `:pressure-drop-Pa`,
  `:delivery-pressure-Pa`, `:feasible?`, `:shortfall-pressure-Pa` (0.0 when
  feasible — never an exception), the caller's provenance echoed, and the
  explicit unmeasured envelope."
  [{:keys [mass-flow-kg-s upstream-pressure-Pa min-delivery-pressure-Pa
           length-m diameter-m friction-factor density-kg-m3 line-source]
    :as input}]
  (positive! input [:mass-flow-kg-s :upstream-pressure-Pa
                    :min-delivery-pressure-Pa :length-m :diameter-m
                    :density-kg-m3])
  (when-not (and (finite-number? friction-factor)
                 (< 0.0 (double friction-factor) 1.0))
    (throw (ex-info "h2-line-drop :friction-factor must be a finite Darcy friction factor in (0, 1)"
                    {:field :friction-factor :value friction-factor})))
  (nonblank-string! input :line-source)
  (let [area-m2  (* pi (/ (* (double diameter-m) (double diameter-m)) 4.0))
        v-m-s    (/ (double mass-flow-kg-s) (* (double density-kg-m3) area-m2))
        dp-pa    (* (double friction-factor)
                    (/ (double length-m) (double diameter-m))
                    (double density-kg-m3)
                    (/ (* v-m-s v-m-s) 2.0))
        p-out    (- (double upstream-pressure-Pa) dp-pa)
        p-min    (double min-delivery-pressure-Pa)
        feasible? (>= p-out p-min)
        shortfall (if feasible? 0.0 (max 0.0 (- p-min p-out)))]
    (cond-> {:solver :h2-line-drop
             :model "steady Darcy-Weisbach: dP = f·(L/D)·rho·v²/2; p-out = p-in − dP"
             :fidelity :reduced-order
             :status :screening-only
             :units :SI
             :assumptions [:steady-flow :incompressible-at-caller-density
                           :darcy-friction-factor :straight-line-no-fittings
                           :absolute-pressures]
             :mass-flow-kg-s mass-flow-kg-s
             :upstream-pressure-Pa upstream-pressure-Pa
             :min-delivery-pressure-Pa min-delivery-pressure-Pa
             :length-m length-m
             :diameter-m diameter-m
             :friction-factor friction-factor
             :density-kg-m3 density-kg-m3
             :flow-area-m2 area-m2
             :velocity-m-s v-m-s
             :pressure-drop-Pa dp-pa
             :delivery-pressure-Pa p-out
             :feasible? feasible?
             :shortfall-pressure-Pa shortfall
             :line-source line-source
             :unmeasured {:compressibility-along-line true
                          :fittings-and-minor-losses true
                          :entrance-exit-losses true
                          :joule-thomson-and-two-phase-effects true
                          :leak-rate true
                          :transient-startup true}}
        (:case/id input) (assoc :case/id (:case/id input))
        (:case/provenance input) (assoc :case/provenance (:case/provenance input)))))

(defmethod cae.solver/solve :h2-line-drop [case]
  (h2-line-drop case))
