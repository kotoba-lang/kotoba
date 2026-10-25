(ns uvm.phase
  "The 9 standard UVM phases (Accellera UVM, accellera.org) plus a real
  phasing engine: `run-phases` executes every phase, in order, across
  an entire `uvm.component` tree, using the standard uvm_component
  convention that a phase callback runs top-down — parent components
  before their children. There is no objection/drain-time mechanics,
  no domain phasing, and no parallel run-phase forking here; this is
  a single deterministic pass through the schedule."
  (:require [uvm.component :as component]))

(def phases
  "The UVM common-phase schedule, in execution order: build through
  connect and elaboration, into run, then the report-side phases."
  [:build-phase :connect-phase :end-of-elaboration-phase
   :start-of-simulation-phase :run-phase :extract-phase
   :check-phase :report-phase :final-phase])

(defn phase-index
  "The position of `phase` within `phases`, or nil if it is not part
  of the standard schedule. Useful for asserting that one phase ran
  before another."
  [phase]
  (first (keep-indexed (fn [i p] (when (= p phase) i)) phases)))

(defn run-phase
  "Run a single `phase` across `root`'s whole tree, top-down (via
  `uvm.component/walk`), threading `state` through every component
  that has a callback registered for `phase`. A callback has the
  signature `(fn [comp phase state] new-state)`; components with no
  matching callback are skipped and `state` passes through unchanged."
  [root phase state]
  (reduce (fn [s c]
            (if-let [cb (get-in c [:callbacks phase])]
              (cb c phase s)
              s))
          state
          (component/walk root)))

(defn run-phases
  "Run every phase in `phases`, in order, over `root`'s component
  tree, dispatching each component's `phase`-keyed :callbacks entry
  (if present) and threading the accumulated `state` (default `{}`)
  through the entire run. Returns the final state after
  :final-phase — the phase-major, tree-minor order this produces
  (every component's :build-phase before any component's
  :connect-phase, and so on) mirrors UVM's real phasing discipline."
  ([root] (run-phases root {}))
  ([root init-state]
   (reduce (fn [state phase] (run-phase root phase state))
           init-state
           phases)))
