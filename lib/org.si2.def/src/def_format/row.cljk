(ns def-format.row
  "DEF ROWS/TRACKS section: the placement-site grid (ROW) and routing
  track grid (TRACKS) of a placed-and-routed design (Si2 DEF, si2.org).")

(defn row
  [name site origin orientation num-x step-x]
  {:name name :site site :origin origin :orientation orientation
   :num-x num-x :step-x step-x})

(defn track
  [layer direction start step count]
  {:layer layer :direction direction :start start :step step :count count})

(defn row-total-width
  "Total x-extent spanned by a row's repeated placement sites: the
  distance from the row's origin to the far edge of its last site column
  (`num-x * step-x`, in DEF database units)."
  [r]
  (* (:num-x r) (:step-x r)))
