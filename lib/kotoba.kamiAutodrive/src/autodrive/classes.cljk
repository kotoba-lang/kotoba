(ns autodrive.classes
  "Per-vehicle-class kinematic limits.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  FIDELITY MAP. Every class has a physics plant of its own (see
  `autodrive.dynamics` and `autodrive.plant`); these limits only scale the
  shared guidance/navigation/control loop:

  - `:car` — kinematic `autodrive.plant/bicycle-model` (the original crate's
    `kami-vehicle` BeamNG soft-body `soft-body-car` feature is excluded — see
    the README for rationale).
  - `:ship` — `autodrive.dynamics/ship-hydro`: Fossen 3-DOF surge/sway/yaw,
    added mass, quadratic damping, rudder.
  - `:drone` — `autodrive.dynamics/multirotor`: thrust-vector tilt + aero
    drag + yaw + sideslip damping.
  - `:aircraft` — `autodrive.dynamics/fixed-wing`: lift/drag, ISA density,
    stall, bank-to-turn.

  Honest caveats remain: the non-car plants are reduced-order (3-DOF point /
  coordinated-turn), not full 6-DOF CFD; the aircraft holds cruise altitude
  and cannot hover (it overflies a goal rather than stopping).")

(def vehicle-classes [:car :ship :drone :aircraft])

(defn limits
  "Class-representative kinematic limits."
  [class]
  (case class
    ;; Matches a mid-size sedan (kami-vehicle default).
    :car {:max-speed 25.0 :max-accel 4.0 :max-decel 8.0 :wheelbase 2.7
          :max-steer 0.61 :turn-radius-ref 4.5 :footprint-radius 1.3}
    ;; Small civilian vessel: slow, wide turns, gentle accel.
    :ship {:max-speed 8.0 :max-accel 0.5 :max-decel 1.0 :wheelbase 30.0
           :max-steer 0.52 :turn-radius-ref 40.0 :footprint-radius 6.0}
    ;; Ground-projected agile multirotor.
    :drone {:max-speed 15.0 :max-accel 6.0 :max-decel 6.0 :wheelbase 0.5
            :max-steer 1.20 :turn-radius-ref 2.5 :footprint-radius 0.6}
    ;; Fixed-wing on taxi / coordinated-turn projection.
    :aircraft {:max-speed 60.0 :max-accel 3.0 :max-decel 4.0 :wheelbase 15.0
               :max-steer 0.35 :turn-radius-ref 250.0 :footprint-radius 8.0}))
