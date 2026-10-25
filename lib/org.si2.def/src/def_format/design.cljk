(ns def-format.design
  "DEF (Design Exchange Format) top-level DESIGN/UNITS/DIEAREA model (Si2,
  Silicon Integration Initiative, si2.org — companion format to LEF: LEF
  describes reusable standard-cell/IP physical abstracts, DEF describes an
  actual placed-and-routed design instance built from them).")

(defn design
  "Build a DESIGN map. `die-area` is `[x1 y1 x2 y2]` in DEF database
  units; `units-distance-microns` is the DB-units-per-micron scale factor
  from the UNITS DISTANCE MICRONS statement (e.g. 1000)."
  [name units-distance-microns die-area]
  {:name name
   :units-distance-microns units-distance-microns
   :die-area die-area})

(defn die-area-um2
  "Compute the die area in square microns from a DESIGN map's :die-area
  rect (DEF database units) and :units-distance-microns scale factor."
  [{:keys [die-area units-distance-microns]}]
  (when (and die-area units-distance-microns (pos? units-distance-microns))
    (let [[x1 y1 x2 y2] die-area
          width-um (/ (double (Math/abs (- x2 x1))) units-distance-microns)
          height-um (/ (double (Math/abs (- y2 y1))) units-distance-microns)]
      (* width-um height-um))))
