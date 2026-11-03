(ns kotoba.swarm-choreo.gate
  "Show-lifecycle actions layered on `kotoba-lang/robotics`' generic
  mission/action/governor contract (ADR-2607011000). Mirrors
  `kotoba.teleop.governor`'s shape exactly: a thin, product-specific
  wrapper that supplies default safety classes to `kotoba.robotics`'
  constructors — it does not redefine `gate`; callers call
  `kotoba.robotics/gate` directly.

  Every show-lifecycle transition is a `kotoba.robotics/action`: routine
  formation playback defaults to `:low`/`:medium` (the posture teleop's
  `:crawl`/`:normal` speed modes carry); arm and takeoff default to
  `:safety-critical`/`:high`, so `kotoba.robotics/gate` always routes them
  to `:require-sign-off`, however permissive the operator's allowed
  safety-class set is — the same mechanism that makes teleop's turbo mode
  safe by construction, applied to a physically higher-stakes phase (a
  live multirotor leaving the ground).

  `abort-all` bypasses the gate entirely, exactly like teleop's e-stop
  chord and deadman-release stop: an all-abort must never wait on a
  permission check."
  (:require [kotoba.robotics :as rob]))

(def phase-safety
  "Default `kotoba.robotics` safety class per show-lifecycle phase.
  `:arm`/`:takeoff`/`:land` are the phases that actually leave/return to
  the ground and default to human-sign-off classes; `:formation-change`
  and routine `:playback` default to classes that do not require sign-off
  (an operator/governor may still choose a stricter allowed set)."
  {:arm :safety-critical
   :takeoff :high
   :formation-change :medium
   :playback :low
   :land :high})

(defn show-action
  "A `kotoba.robotics/action` for `phase` (a key of `phase-safety`, or any
  keyword — unknown phases default to `:medium`). `:safety` overrides the
  phase default; `:params` is merged with `{:phase phase}`."
  [id mission-id phase & {:keys [safety params]}]
  (rob/action id mission-id :actuate
              (or safety (get phase-safety phase :medium))
              :params (assoc params :phase phase)))

(defn abort-all
  "An all-abort `kotoba.robotics/safety-stop` for `mission-id` — bypasses
  `kotoba.robotics/gate` entirely, per the namespace docstring. `:reason`
  defaults to `:operator` (a deliberate abort); pass `:e-stop` for a
  hardware/operator emergency-stop trigger, or `:boundary` for a geofence
  breach (see `kotoba.swarm-choreo.validate/geofence-violations`)."
  [mission-id & {:keys [reason source detail] :or {reason :operator}}]
  (rob/safety-stop mission-id reason :source source :detail detail))
