(ns engineer.grid
  "Grid config + point-snap. Restored from kami-eng-core's `grid`/`snap`
  modules (deleted PR #82). Default spacing 2.54 (100mil, standard EDA grid).")

(defn config
  "A grid config at `spacing` (default 2.54 — 100mil standard EDA grid)."
  ([] (config 2.54))
  ([spacing]
   {:spacing spacing :major-every 10 :origin [0.0 0.0]
    :visible true :snap-enabled true}))

(defn snap-to-grid
  "Snap `[x y]` to the nearest grid intersection per `grid`'s spacing/origin.
  Returns `point` unchanged if `:snap-enabled` is false."
  [[x y] grid]
  (if (:snap-enabled grid)
    (let [{:keys [spacing origin]} grid
          [ox oy] origin
          snap1 (fn [v o] (+ (* (Math/round (double (/ (- v o) spacing))) spacing) o))]
      [(snap1 x ox) (snap1 y oy)])
    [x y]))
