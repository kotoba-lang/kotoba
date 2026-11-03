(ns vehicle.models.sedan
  "Reference sedan model -- a 4-door, FWD, 2.0L NA car.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   Granularity matches the BeamNG \"Pessima\" base car at the structural
   level: 24 chassis nodes (8 floor / 8 belt / 8 roof) + 4 cargo nodes +
   2 subframe nodes + 4 unsprung axles x 2 nodes = 8 wheel-hub nodes +
   4 tire rings x 12 nodes = 48 tire nodes (~86 nodes total), ~220 beams
   (chassis cross-bracing + suspension + tire side-walls + tire tread).

   Coordinates: +x = right, +y = up, +z = forward. Origin at the centre
   of the rear axle on the ground plane.

   This is a straight port of `sedan()` in the original Rust. Since the
   Rust version mutates a `&mut VehicleBuilder` imperatively while
   assembling ~90 nodes and ~220 beams, this port uses a local (function-
   scoped, non-escaping) atom wrapping `vehicle.builder`'s immutable
   builder value to preserve the exact same imperative shape and
   readability -- the function as a whole remains referentially
   transparent."
  (:require [vehicle.vec3 :as v3]
            [vehicle.beam :as beam]
            [vehicle.builder :as builder]
            [vehicle.powertrain :as pt]
            [vehicle.triangle :as triangle]
            [vehicle.wheel :as wheel]))

(defn default-spec []
  {:wheelbase 2.70 :track-width 1.55 :ride-height 0.55 :roof-height 1.00
   :overhang-front 0.95 :overhang-rear 1.10
   :mass-chassis 820.0 :mass-engine 260.0 :mass-cabin 540.0
   :wheel-radius 0.32 :wheel-width 0.22
   :layout (pt/layout-fwd) :turbo false})

(defn sedan [spec]
  (let [b (atom (builder/new-builder "sedan"))
        node! (fn [pos mass group]
                (let [[b' id] (builder/node! @b pos mass group)] (reset! b b') id))
        beam! (fn [n1 n2 spring damping]
                (let [[b' id] (builder/beam! @b n1 n2 spring damping)] (reset! b b') id))
        beam-typed! (fn [n1 n2 spring damping ty deform bg]
                      (let [[b' id] (builder/beam-typed! @b n1 n2 spring damping ty deform bg)] (reset! b b') id))
        triangle! (fn [n1 n2 n3 group]
                    (let [[b' id] (builder/triangle! @b n1 n2 n3 group)] (reset! b b') id))
        wheel! (fn [a1 a2 r w tire]
                 (let [[b' id] (builder/wheel! @b a1 a2 r w tire)] (reset! b b') id))
        add-tire-ring! (fn [wid centre axis radius cnt nm sp da rp]
                          (let [[b' ids] (builder/add-tire-ring! @b wid centre axis radius cnt nm sp da rp)]
                            (reset! b b') ids))

        h-floor (:ride-height spec)
        h-belt (+ (:ride-height spec) (* (:roof-height spec) 0.55))
        h-roof (+ (:ride-height spec) (:roof-height spec))
        half-w (* (:track-width spec) 0.5)
        z-rear (- (:overhang-rear spec))
        z-front (+ (:wheelbase spec) (:overhang-front spec))
        z-rear-axle 0.0
        z-front-axle (:wheelbase spec)

        chassis-node-mass (/ (:mass-chassis spec) 24.0)
        cabin-node-mass (/ (:mass-cabin spec) 8.0)

        ;; ---- Floor frame (8 nodes) ----
        f-rl (node! (v3/v3 (- half-w) h-floor z-rear) chassis-node-mass :body)
        f-rr (node! (v3/v3 half-w h-floor z-rear) chassis-node-mass :body)
        f-rxl (node! (v3/v3 (- half-w) h-floor z-rear-axle) chassis-node-mass :body)
        f-rxr (node! (v3/v3 half-w h-floor z-rear-axle) chassis-node-mass :body)
        f-fxl (node! (v3/v3 (- half-w) h-floor z-front-axle) chassis-node-mass :body)
        f-fxr (node! (v3/v3 half-w h-floor z-front-axle) chassis-node-mass :body)
        f-fl (node! (v3/v3 (- half-w) h-floor z-front) chassis-node-mass :body)
        f-fr (node! (v3/v3 half-w h-floor z-front) chassis-node-mass :body)

        ;; ---- Belt-line (8 nodes) ----
        g-rl (node! (v3/v3 (- half-w) h-belt z-rear) cabin-node-mass :body)
        g-rr (node! (v3/v3 half-w h-belt z-rear) cabin-node-mass :body)
        g-rxl (node! (v3/v3 (- half-w) h-belt z-rear-axle) cabin-node-mass :body)
        g-rxr (node! (v3/v3 half-w h-belt z-rear-axle) cabin-node-mass :body)
        g-fxl (node! (v3/v3 (- half-w) h-belt z-front-axle) cabin-node-mass :body)
        g-fxr (node! (v3/v3 half-w h-belt z-front-axle) cabin-node-mass :body)
        g-fl (node! (v3/v3 (- half-w) h-belt z-front) cabin-node-mass :body)
        g-fr (node! (v3/v3 half-w h-belt z-front) cabin-node-mass :body)

        ;; ---- Roof (8 nodes) ----
        r-rl (node! (v3/v3 (* (- half-w) 0.85) h-roof (+ z-rear 0.10)) chassis-node-mass :body)
        r-rr (node! (v3/v3 (* half-w 0.85) h-roof (+ z-rear 0.10)) chassis-node-mass :body)
        r-rxl (node! (v3/v3 (* (- half-w) 0.85) h-roof (+ z-rear-axle 0.30)) chassis-node-mass :body)
        r-rxr (node! (v3/v3 (* half-w 0.85) h-roof (+ z-rear-axle 0.30)) chassis-node-mass :body)
        r-fxl (node! (v3/v3 (* (- half-w) 0.85) h-roof (- z-front-axle 0.30)) chassis-node-mass :body)
        r-fxr (node! (v3/v3 (* half-w 0.85) h-roof (- z-front-axle 0.30)) chassis-node-mass :body)
        r-fl (node! (v3/v3 (* (- half-w) 0.85) (- h-roof 0.10) (+ z-front-axle 0.20)) chassis-node-mass :body)
        r-fr (node! (v3/v3 (* half-w 0.85) (- h-roof 0.10) (+ z-front-axle 0.20)) chassis-node-mass :body)

        ;; ---- Cargo (engine block + battery + fuel tank, 4 nodes) ----
        engine-mass (/ (:mass-engine spec) 2.0)
        tank-mass 30.0
        battery-mass 22.0
        cargo-l (node! (v3/v3 -0.30 (+ h-floor 0.20) (- z-front-axle 0.30)) engine-mass :cargo)
        cargo-r (node! (v3/v3 0.30 (+ h-floor 0.20) (- z-front-axle 0.30)) engine-mass :cargo)
        _battery (node! (v3/v3 -0.40 (+ h-floor 0.30) (- z-front-axle 0.10)) battery-mass :cargo)
        _tank (node! (v3/v3 0.0 (+ h-floor 0.05) (+ z-rear-axle 0.40)) tank-mass :cargo)

        ;; ---- Chassis frame beams ----
        estimated-mass (max (+ (:mass-chassis spec) (:mass-engine spec) (:mass-cabin spec)) 1000.0)
        mass-factor (/ estimated-mass 1500.0)
        frame-spring (* 8000000.0 mass-factor)
        frame-damping (* 4000.0 (Math/sqrt mass-factor))
        cabin-spring (* 5000000.0 mass-factor)
        cabin-damping (* 2000.0 (Math/sqrt mass-factor))
        crush-deform {:deform-limit 0.30 :break-limit 0.85 :max-plastic-strain 0.50}
        panel-deform {:deform-limit 0.30 :break-limit 0.85 :max-plastic-strain 0.50}
        _ (doseq [[a c] [[f-rl f-rxl] [f-rxl f-fxl] [f-fxl f-fl]
                          [f-rr f-rxr] [f-rxr f-fxr] [f-fxr f-fr]]]
            (beam-typed! a c frame-spring frame-damping beam/beam-type-normal crush-deform 1))
        _ (doseq [[a c] [[f-rl f-rr] [f-rxl f-rxr] [f-fxl f-fxr] [f-fl f-fr]]]
            (beam-typed! a c frame-spring frame-damping beam/beam-type-normal crush-deform 1))
        _ (doseq [[a c] [[f-rl f-rxr] [f-rxl f-fxr] [f-fxl f-fr]]]
            (beam-typed! a c (* frame-spring 0.6) frame-damping beam/beam-type-normal crush-deform 1))

        _ (doseq [[low mid high] [[f-rl g-rl r-rl] [f-rr g-rr r-rr]
                                   [f-rxl g-rxl r-rxl] [f-rxr g-rxr r-rxr]
                                   [f-fxl g-fxl r-fxl] [f-fxr g-fxr r-fxr]
                                   [f-fl g-fl r-fl] [f-fr g-fr r-fr]]]
            (do (beam-typed! low mid cabin-spring cabin-damping beam/beam-type-normal panel-deform 2)
                (beam-typed! mid high cabin-spring cabin-damping beam/beam-type-normal panel-deform 2)))

        _ (doseq [[a c] [[g-rl g-rxl] [g-rxl g-fxl] [g-fxl g-fl]
                          [g-rr g-rxr] [g-rxr g-fxr] [g-fxr g-fr]
                          [g-rl g-rr] [g-fl g-fr]]]
            (beam-typed! a c cabin-spring cabin-damping beam/beam-type-normal panel-deform 2))

        _ (doseq [[a c] [[r-rl r-rxl] [r-rxl r-fxl] [r-fxl r-fl]
                          [r-rr r-rxr] [r-rxr r-fxr] [r-fxr r-fr]
                          [r-rl r-rr] [r-fl r-fr]]]
            (beam-typed! a c (* cabin-spring 0.7) cabin-damping beam/beam-type-normal panel-deform 3))

        _ (doseq [[a c] [[cargo-l f-fxl] [cargo-l f-fxr] [cargo-l f-fl]
                          [cargo-r f-fxl] [cargo-r f-fxr] [cargo-r f-fr]
                          [cargo-l cargo-r]]]
            (beam-typed! a c frame-spring frame-damping beam/beam-type-normal crush-deform 4))

        ;; ---- Subframe nodes ----
        subframe-mass 8.0
        sf-front (node! (v3/v3 0.0 (:wheel-radius spec) z-front-axle) subframe-mass :body)
        sf-rear (node! (v3/v3 0.0 (:wheel-radius spec) z-rear-axle) subframe-mass :body)

        strut-deform {:deform-limit 0.50 :break-limit 0.95 :max-plastic-strain 0.40}
        strut-k (* frame-spring 1.5)
        strut-d (* 2.0 0.7 (Math/sqrt (* strut-k subframe-mass)))
        _ (doseq [[sub n1 n2] [[sf-front f-fxl f-fxr] [sf-rear f-rxl f-rxr]]]
            (do (beam-typed! sub n1 strut-k strut-d beam/beam-type-normal strut-deform 5)
                (beam-typed! sub n2 strut-k strut-d beam/beam-type-normal strut-deform 5)))
        _ (beam-typed! sf-front sf-rear frame-spring strut-d beam/beam-type-normal strut-deform 5)

        ;; ---- Wheel hubs + suspension ----
        hub-mass (+ 14.0 (* (- mass-factor 1.0) 8.0))
        target-deflection 0.001
        per-corner-load (/ (* estimated-mass 9.81) 4.0)
        spring-stiff (max (/ per-corner-load target-deflection) 5000000.0)
        zeta 0.45
        spring-damping (* 2.0 zeta (Math/sqrt (* spring-stiff (/ estimated-mass 4.0))))
        elastic {:deform-limit 1.5 :break-limit 3.0 :max-plastic-strain 0.0}
        arm-deform {:deform-limit 2.0 :break-limit 5.0 :max-plastic-strain 0.0}
        arm-spring (max (/ spring-stiff 12.0) 4000.0)
        arm-damping (* spring-damping 1.5)

        make-wheel
        (fn [x z subframe mount-high]
          (let [hub-y (:wheel-radius spec)
                hub-x-in (- x 0.10)
                hub-x-out (+ x 0.10)
                h-in (node! (v3/v3 hub-x-in hub-y z) (* hub-mass 0.5) :wheel-hub)
                h-out (node! (v3/v3 hub-x-out hub-y z) (* hub-mass 0.5) :wheel-hub)]
            (beam-typed! mount-high h-in (* spring-stiff 0.5) (* spring-damping 0.5) beam/beam-type-normal elastic nil)
            (beam-typed! mount-high h-out (* spring-stiff 0.5) (* spring-damping 0.5) beam/beam-type-normal elastic nil)
            (beam-typed! subframe h-in (* arm-spring 4.0) arm-damping beam/beam-type-normal arm-deform nil)
            (beam-typed! subframe h-out (* arm-spring 4.0) arm-damping beam/beam-type-normal arm-deform nil)
            (let [wheel-id (wheel! h-in h-out (:wheel-radius spec) (:wheel-width spec) (wheel/pacejka-road-dry))]
              (add-tire-ring! wheel-id (v3/v3 (* (+ hub-x-in hub-x-out) 0.5) hub-y z) v3/unit-x
                               (:wheel-radius spec) 12 0.30 120000.0 450.0 2.4)
              wheel-id)))

        _wfl (make-wheel (- half-w) z-front-axle sf-front g-fxl)
        _wfr (make-wheel half-w z-front-axle sf-front g-fxr)
        _wrl (make-wheel (- half-w) z-rear-axle sf-rear g-rxl)
        _wrr (make-wheel half-w z-rear-axle sf-rear g-rxr)

        ;; ---- Body panel triangles ----
        _ (doseq [[t1 t2 t3] [[f-rl f-rxl f-rr] [f-rxl f-rxr f-rr]
                               [f-rxl f-fxl f-rxr] [f-fxl f-fxr f-rxr]
                               [f-fxl f-fl f-fxr] [f-fl f-fr f-fxr]]]
            (triangle! t1 t2 t3 :underbody))
        side-pairs-left [[f-rl g-rl] [f-rxl g-rxl] [f-fxl g-fxl] [f-fl g-fl]]
        side-pairs-right [[f-rr g-rr] [f-rxr g-rxr] [f-fxr g-fxr] [f-fr g-fr]]
        _ (doseq [[[a-lo a-hi] [b-lo b-hi]] (partition 2 1 side-pairs-left)]
            (do (triangle! a-lo a-hi b-hi :body) (triangle! a-lo b-hi b-lo :body)))
        _ (doseq [[[a-lo a-hi] [b-lo b-hi]] (partition 2 1 side-pairs-right)]
            (do (triangle! a-lo b-hi a-hi :body) (triangle! a-lo b-lo b-hi :body)))
        upper-left [[g-rl r-rl] [g-rxl r-rxl] [g-fxl r-fxl] [g-fl r-fl]]
        upper-right [[g-rr r-rr] [g-rxr r-rxr] [g-fxr r-fxr] [g-fr r-fr]]
        _ (doseq [[[a-lo a-hi] [b-lo b-hi]] (partition 2 1 upper-left)]
            (do (triangle! a-lo a-hi b-hi :window) (triangle! a-lo b-hi b-lo :window)))
        _ (doseq [[[a-lo a-hi] [b-lo b-hi]] (partition 2 1 upper-right)]
            (do (triangle! a-lo b-hi a-hi :window) (triangle! a-lo b-lo b-hi :window)))
        _ (doseq [[t1 t2 t3] [[r-rl r-rxl r-rr] [r-rxl r-rxr r-rr]
                               [r-rxl r-fxl r-rxr] [r-fxl r-fxr r-rxr]
                               [r-fxl r-fl r-fxr] [r-fl r-fr r-fxr]]]
            (triangle! t1 t2 t3 :body))
        _ (doseq [[t1 t2 t3] [[g-fxl g-fxr g-fr] [g-fxl g-fr g-fl]]] (triangle! t1 t2 t3 :body))
        _ (doseq [[t1 t2 t3] [[g-rxl g-rxr g-rr] [g-rxl g-rr g-rl]]] (triangle! t1 t2 t3 :body))
        _ (doseq [[t1 t2 t3] [[f-fl f-fr g-fr] [f-fl g-fr g-fl]]] (triangle! t1 t2 t3 :body))
        _ (doseq [[t1 t2 t3] [[f-rl f-rr g-rr] [f-rl g-rr g-rl]]] (triangle! t1 t2 t3 :body))
        _ (doseq [[t1 t2 t3] [[g-fxl g-fxr r-fr] [g-fxl r-fr r-fl]]] (triangle! t1 t2 t3 :window))
        _ (doseq [[t1 t2 t3] [[g-rxl g-rxr r-rr] [g-rxl r-rr r-rl]]] (triangle! t1 t2 t3 :window))

        vehicle0 (builder/build @b)

        actual-load-per-corner (/ (* (:total-mass vehicle0) 9.81) 4.0)
        actual-def (min 0.20 (max 0.0 (/ actual-load-per-corner spring-stiff)))
        actual-tire-pen (min 0.080 (max 0.005 (/ actual-load-per-corner 100000.0)))
        body-shift (+ actual-def actual-tire-pen)
        vehicle1 (update vehicle0 :nodes
                          (fn [nodes]
                            (mapv (fn [n]
                                    (-> (case (:group n)
                                          :body (update n :position update :y - body-shift)
                                          :cargo (update n :position update :y - body-shift)
                                          :wheel-hub (update n :position update :y - actual-tire-pen)
                                          :wheel-tire (update n :position update :y - actual-tire-pen)
                                          n)
                                        (assoc :velocity v3/zero)))
                                  nodes)))

        curve (if (:turbo spec) (pt/turbo-2-0) (pt/na-2-0-gasoline))
        pwr (-> (pt/sedan-powertrain)
                (assoc-in [:engine :torque-curve] curve)
                (assoc :layout (:layout spec)))
        pwr (if (= :awd (:kind (:layout spec)))
              (assoc pwr :front-diff (pt/diff-lsd 0.40) :rear-diff (pt/diff-lsd 0.40))
              pwr)
        vehicle2 (assoc vehicle1 :powertrain pwr)]
    vehicle2))
