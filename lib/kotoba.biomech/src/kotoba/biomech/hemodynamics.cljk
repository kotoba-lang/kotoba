(ns kotoba.biomech.hemodynamics
  "Blood-flow / airflow CFD via kotoba-lang/kami-engine-cfd (Phase 2 backend).

  Bridges into the D2Q9 Lattice-Boltzmann solver: a 2-D channel with
  no-slip top/bottom walls, a left inlet velocity, and a zero-gradient
  right outlet (these BCs are applied by kami-cfd/lbm-new). An obstacle
  in the channel — a vessel cross-section, an atheromatous plaque, an
  airway constriction — yields a drag the flow exerts on it, a proxy for
  wall shear / flow resistance. Reynolds number is based on obstacle
  height."
  (:require [kami-cfd :as cfd]))

(defn channel-with-obstacle
  "Build a 2-D channel `nx` by `ny` lattice cells with a rectangular
  obstacle of width `ow` [cells] and height `oh` [cells] at x-offset
  `ox` [cells]. Returns a kami-cfd Body."
  [nx ny ox ow oh]
  (cfd/block nx ny ox ow oh))

(defn new-flow
  "Initialize the LBM state for `body` at Reynolds number `re` (based on
  obstacle height). Inlet / outlet / wall boundary conditions are applied
  by the solver."
  [body re]
  (cfd/lbm-new body re))

(defn step-flow
  "Advance the LBM one step. Returns [lbm' drag-this-step]."
  [lbm]
  (cfd/step lbm))

(defn obstacle-drag-cd
  "Averaged sectional drag coefficient the flow exerts on the obstacle in
  `body`, at Reynolds `re`, over `steps` LBM steps. A higher Cd means more
  flow resistance (narrower / blunter obstacle)."
  [body re steps]
  (cfd/sectional-cd body re steps))

(defn velocity-at
  "[ux uy] velocity at lattice position (x, y), or nil if the cell is solid
  or out of range. Thin pass-through to kami-cfd/velocity-at (now public).
  Use to read back a flow probe after stepping."
  [lbm x y]
  (cfd/velocity-at lbm x y))

(defn density-at
  "Density rho at lattice position (x, y), or nil if solid / out of range."
  [lbm x y]
  (cfd/density-at lbm x y))
