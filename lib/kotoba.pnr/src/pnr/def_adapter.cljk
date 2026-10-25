(ns pnr.def-adapter
  "Bridges pnr.placement output into org-si2-def (Si2 DEF placed-design
  exchange format): converts `pnr.placement/place-cells` output cells into
  `def-format.component` records and assembles a DEF-shaped design map, so
  a pnr placement run can be exported as a standard, more interoperable
  DEF file alongside (or instead of) `pnr.gdsii`'s GDSII-only export."
  (:require [def-format.component :as def-component]))

(defn placed-cell->def-component
  "Convert one `pnr.placement/place-cells` output cell
  (`{:cell-name :instance-name :x :y :orientation :row-idx}`) into a
  `def-format.component/component` record. DEF locations are in microns,
  not pnr's site/row units, so `:x`/`:row-idx` are scaled by
  `site-width-um`/`site-height-um` to get `[x-um y-um]`. Defaults to
  `1.0`/`1.0` (i.e. raw site-units passed through unscaled) when the
  caller doesn't need real microns. Status is always `:placed` -- this
  adapter only ever sees cells that `place-cells` has already placed."
  ([placed-cell] (placed-cell->def-component placed-cell 1.0 1.0))
  ([placed-cell site-width-um site-height-um]
   (def-component/component
     (:instance-name placed-cell)
     (:cell-name placed-cell)
     :placed
     [(* (:x placed-cell) site-width-um)
      (* (:row-idx placed-cell) site-height-um)]
     (:orientation placed-cell))))

(defn placement->def-design
  "Build a full org-si2-def-shaped design map from a `pnr.placement`
  placement (`{:rows :cells}`, e.g. `pnr.placement/place-cells`'s return
  value): a DESIGN header (`def-format.design`-shaped) plus a COMPONENTS
  list built from the placed cells. `:nets` and `:tracks` are left empty
  -- this adapter's job is the placement/component side of DEF export,
  not full netlist/routing DEF export."
  [design-name placement site-width-um site-height-um die-width-um die-height-um]
  {:design {:name design-name
            :units-distance-microns 1000
            :die-area [0.0 0.0 die-width-um die-height-um]}
   :components (mapv #(placed-cell->def-component % site-width-um site-height-um)
                      (:cells placement))
   :nets []
   :rows (:rows placement)
   :tracks []})
