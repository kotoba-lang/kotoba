(ns floorplan-lab.ble
  "BLE RSSI trilateration: convert RSSI readings from known-position
  beacons into distances (free-space log-distance path-loss model), then
  trilaterate a 2D position via linear least squares. Part of the indoor
  floorplan-lab (ADR-2607140600 Phase 3a device-capability bridge) --
  SOFTWARE ONLY, no real CoreBluetooth involved; readings are either
  `floorplan-lab.sensing-bridge`-adapted driver output or, in this lab's
  tests, synthetic data.")

;; ---------- portable math ----------

#?(:clj (defn- pow ^double [^double b ^double e] (Math/pow b e))
   :cljs (defn- pow [b e] (js/Math.pow b e)))

#?(:clj (defn- sqrt ^double [^double x] (Math/sqrt x))
   :cljs (defn- sqrt [x] (js/Math.sqrt x)))

(def default-tx-power-at-1m-dbm
  "RSSI expected at exactly 1m from a typical BLE beacon -- the usual
  starting calibration constant for the log-distance path-loss model.
  Real deployments should calibrate this per-beacon (future work, see
  README)."
  -59.0)

(def default-path-loss-exponent
  "N in the log-distance path loss model. 2.0 = free-space / line-of-
  sight; indoor multi-wall environments are typically higher (2.5-4.0).
  Documented as a starting point, not a universal constant -- callers
  should recalibrate per-site (future work, see README)."
  2.0)

(defn rssi->distance-m
  "Free-space log-distance path loss model: distance =
  10^((tx-power-at-1m - rssi) / (10*n)). RSSI and TX-POWER-AT-1M in dBm,
  N = path-loss exponent."
  ([rssi] (rssi->distance-m rssi default-tx-power-at-1m-dbm default-path-loss-exponent))
  ([rssi tx-power-at-1m] (rssi->distance-m rssi tx-power-at-1m default-path-loss-exponent))
  ([rssi tx-power-at-1m n]
   (pow 10.0 (/ (- tx-power-at-1m rssi) (* 10.0 n)))))

(defn trilaterate
  "Linear-least-squares trilateration from >= 3 BEACONS ({:x :y :distance}
  maps, distance already in meters -- e.g. via `rssi->distance-m`). Uses
  the standard linearization: subtract the LAST beacon's circle equation
  from every other beacon's to cancel the quadratic (x^2+y^2) term,
  giving a linear system solved by 2x2 normal equations (least squares
  over all non-last beacons, exact when the system is consistent -- e.g.
  noise-free synthetic distances). Returns [x y], or nil if fewer than 3
  beacons are given or the beacons are degenerate (collinear -> singular
  normal-equation matrix)."
  [beacons]
  (when (>= (count beacons) 3)
    (let [bs (vec beacons)
          {lx :x ly :y ld :distance} (last bs)
          others (butlast bs)
          rows (for [{:keys [x y distance]} others]
                 ;; 2*(lx-x)*X + 2*(ly-y)*Y = (d^2 - ld^2) - (x^2+y^2) + (lx^2+ly^2)
                 [(* 2.0 (- lx x))
                  (* 2.0 (- ly y))
                  (+ (- (* distance distance) (* ld ld))
                     (- (+ (* lx lx) (* ly ly)) (+ (* x x) (* y y))))])
          a11 (reduce + (map (fn [[a _ _]] (* a a)) rows))
          a12 (reduce + (map (fn [[a b _]] (* a b)) rows))
          a22 (reduce + (map (fn [[_ b _]] (* b b)) rows))
          b1  (reduce + (map (fn [[a _ c]] (* a c)) rows))
          b2  (reduce + (map (fn [[_ b c]] (* b c)) rows))
          det (- (* a11 a22) (* a12 a12))]
      (when-not (zero? det)
        [(/ (- (* b1 a22) (* b2 a12)) det)
         (/ (- (* a11 b2) (* a12 b1)) det)]))))

(defn position-error-m
  "Euclidean distance between two [x y] points -- convenience for tests
  and for a caller checking how far a fused estimate moved."
  [[x1 y1] [x2 y2]]
  (sqrt (+ (pow (- x1 x2) 2.0) (pow (- y1 y2) 2.0))))
