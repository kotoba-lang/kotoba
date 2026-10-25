(ns ibis.model
  "IBIS Model section: model name, model-type, V-I curve tables for
  pulldown/pullup/power-clamp/gnd-clamp (each an ordered vector of
  [voltage current] points), and ramp-rate ({:dv :dt :r-load}). Includes
  a pure linear-interpolation function over a V-I table.

  Simplified subset of the IBIS Open Forum's IBIS spec (ibis.org): single
  ramp rate (no separate rising/falling), no temperature/voltage-range
  corners, no series models.")

(def model-types
  "Valid `[Model Type]` values this simplified model supports."
  #{:input :output :io :3-state :open-drain})

(defn model
  "An IBIS [Model]: `name`, `model-type` (one of `model-types`, or nil if
  not yet known), V-I curve tables (`pulldown`/`pullup`/`power-clamp`/
  `gnd-clamp`, each a vector of `[voltage current]` points ascending by
  voltage), and `ramp` ({:dv :dt :r-load} — the driver's edge rate into
  `r-load`)."
  [{:keys [name model-type pulldown pullup power-clamp gnd-clamp ramp]
    :or {pulldown [] pullup [] power-clamp [] gnd-clamp []}}]
  {:name name :model-type model-type
   :pulldown pulldown :pullup pullup
   :power-clamp power-clamp :gnd-clamp gnd-clamp
   :ramp ramp})

(defn add-point
  "Return `m` with `[voltage current]` appended to V-I table `table-key`
  (one of :pulldown :pullup :power-clamp :gnd-clamp)."
  [m table-key voltage current]
  (update m table-key (fnil conj []) [voltage current]))

(defn ramp-rate
  "dV/dt (volts per second) implied by ramp `{:dv :dt}`, or nil if either
  is missing or `:dt` is zero."
  [{:keys [dv dt]}]
  (when (and dv dt (not (zero? dt)))
    (/ dv dt)))

(defn interpolate-current
  "Linear-interpolate the current at `voltage` over an ordered V-I
  `table` (a vector of `[v i]` points sorted ascending by `v`). A
  `voltage` outside the table's range clamps to the nearest endpoint's
  current. Returns nil for an empty table."
  [table voltage]
  (when (seq table)
    (let [[v0 i0] (first table)
          [vn in] (last table)]
      (cond
        (<= voltage v0) i0
        (>= voltage vn) in
        :else
        (let [[[v1 i1] [v2 i2]]
              (first (filter (fn [[[v1 _] [v2 _]]] (<= v1 voltage v2))
                              (partition 2 1 table)))]
          (if (== v1 v2)
            i1
            (+ i1 (* (- i2 i1) (/ (- voltage v1) (- v2 v1))))))))))
