(ns kotoba.sarutahiko-factory.loader
  "積込ロボット (finished-truck straddle loader) static config — ported from
  `scene.rs`'s `Loader` struct and the cross-checks the Rust test suite
  ran against it (`loaders_reference_real_carriers_and_vehicles`).

  A single loader entry lives in `:factory/loaders` (see `.factory`) as a
  plain map:

    {:id :kind :pos [x y z] :yaw :size [x y z] :mass
     :payload [x y z] :payload-mass
     :pick [x y]   ; EOL staging pick point
     :drop [x y]   ; carrier drop point
     :deck-z       ; carrier deck height the payload settles onto
     :vehicle}     ; id of the staged-truck render element it removes

  The physical choreography (`LoaderRobot` in `lib.rs`: drive-to-pick →
  kinematically-carry → controlled-lower onto the carrier deck via
  kami-genesis contact) is unported host-adapter physics — this namespace
  keeps only the static config and its pure well-formedness /
  cross-reference checks.

  Pure: no I/O."
  )

(defn- finite-num? [n]
  (and (number? n)
       #?(:clj (Double/isFinite (double n))
          :cljs (js/isFinite n))))

(defn- finite-vec? [v n]
  (and (vector? v) (= n (count v)) (every? finite-num? v)))

(defn valid?
  "True when a loader's numeric fields are well-formed: `:pos`/`:size`/
  `:payload` are finite 3-vectors, `:pick`/`:drop` finite 2-vectors,
  `:mass`/`:payload-mass`/`:deck-z` finite, and `:id`/`:vehicle` non-empty
  strings."
  [loader]
  (and (string? (:id loader)) (seq (:id loader))
       (string? (:vehicle loader)) (seq (:vehicle loader))
       (finite-vec? (:pos loader) 3)
       (finite-vec? (:size loader) 3)
       (finite-vec? (:payload loader) 3)
       (finite-vec? (:pick loader) 2)
       (finite-vec? (:drop loader) 2)
       (finite-num? (:yaw loader))
       (finite-num? (:mass loader))
       (finite-num? (:payload-mass loader))
       (finite-num? (:deck-z loader))
       (pos? (:mass loader))
       (pos? (:payload-mass loader))))

(defn references-known-vehicle?
  "True when `:vehicle` names a real machine id."
  [loader machine-ids]
  (contains? (set machine-ids) (:vehicle loader)))

(defn near-carrier?
  "True when a `\"carrier\"`-kind machine's aabb x-range (expanded by
  `tol`, default 4.0 m, matching the Rust test) contains the loader's
  drop-point x. Mirrors `loaders_reference_real_carriers_and_vehicles`'s
  'a carrier machine must exist near the drop point' check."
  ([loader machines] (near-carrier? loader machines 4.0))
  ([loader machines tol]
   (let [[dx _dy] (:drop loader)]
     (boolean
      (some (fn [m]
              (and (= "carrier" (:kind m))
                   (let [[x0 _y0 x1 _y1] (:aabb m)]
                     (and (>= dx (- x0 tol)) (<= dx (+ x1 tol))))))
            machines)))))
