(ns def-format.component
  "DEF COMPONENTS section: per-instance placement records for a
  placed-and-routed design (Si2 DEF, si2.org — companion to LEF, which
  describes the reusable standard-cell/IP physical abstract that a
  component instantiates via its :cell-ref).")

(def placement-statuses #{:placed :fixed :unplaced :cover})

(defn component
  [instance-name cell-ref status location orientation]
  {:instance-name instance-name
   :cell-ref cell-ref
   :status status
   :location location
   :orientation orientation})

(defn placed?
  "True when a component has a resolved silicon placement (PLACED or
  FIXED), as opposed to UNPLACED (no location assigned yet) or COVER."
  [c]
  (contains? #{:placed :fixed} (:status c)))

(defn placed-components
  "Filter `components` to only those with a resolved placement (:placed or
  :fixed), excluding :unplaced instances."
  [components]
  (filterv placed? components))
