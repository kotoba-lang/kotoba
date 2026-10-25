(ns pnr.lef-adapter
  "Bridges org-si2-lef (Si2 LEF physical cell library) into pnr.placement /
  pnr.gdsii. `pnr.placement/place-cells` only ever knew about hand-picked
  `:width-sites` integers, and `pnr.gdsii/export-gdsii` requires the
  caller to hand it already-resolved geometry (it does no cell-size/
  library lookup of its own) -- this namespace is that missing resolver:
  it turns a LEF macro's real `:size` (physical microns) into a
  placement site-width, and turns a placed cell + its LEF macro into real
  GDSII boundary elements."
  (:require [lef.core :as lef]))

(def layer-number
  "Simplified metal-layer-name -> GDSII layer-number map. A real flow
  carries this mapping in a technology LEF/techfile; hardcoded here as a
  first pass. Unknown layer names fall back to 99."
  {"metal1" 10 "metal2" 11})

(defn- layer->number [layer-name]
  (get layer-number layer-name 99))

(def db-units-per-micron
  "GDSII database units per micron. Matches `pnr.gdsii/export-gdsii`'s
  fixed UNITS record (`[0.001 1e-9]`): 1e-9 meters/db-unit = a nanometer
  db-unit, and 0.001 user-units-per-db-unit means 1 user unit (a micron)
  = 1000 db-units. `pnr.gdsii`'s record writers do bit arithmetic on `:xy`
  values (they must be integers), so every micron value this adapter
  produces is scaled by this factor and rounded before being handed to
  `pnr.gdsii`."
  1000)

(defn- micron->dbu [v]
  (long (Math/round (* (double v) (double db-units-per-micron)))))

(defn- closed-rect-dbu
  "Closed 5-point boundary polygon (GDSII convention: last point repeats
  the first) for rect `[x1 y1 x2 y2]` (microns), offset by `(ox-um oy-um)`
  and converted to GDSII database units."
  [ox-um oy-um x1 y1 x2 y2]
  (mapv (fn [[x y]] [(micron->dbu (+ ox-um x)) (micron->dbu (+ oy-um y))])
        [[x1 y1] [x2 y1] [x2 y2] [x1 y2] [x1 y1]]))

(defn macro->site-width
  "Number of placement sites a LEF `lef-macro`'s physical width occupies,
  given the technology's site width in microns. Rounds up: a cell whose
  width doesn't exactly tile the site grid still needs a whole number of
  sites."
  [lef-macro site-width-um]
  (let [[width-um _height-um] (:size lef-macro)]
    (int (Math/ceil (/ width-um site-width-um)))))

(defn netlist-cell-from-lef
  "Look up `cell-name` in `lef-lib` (an org-si2-lef parsed library, see
  `lef.core/parse-lef`) and build a `pnr.placement`-compatible netlist-cell
  map `{:cell-name :instance-name :width-sites}` from its real LEF SIZE.
  Returns nil if `cell-name` isn't in the library (no macro to resolve a
  width from)."
  [lef-lib cell-name instance-name site-width-um]
  (when-let [macro (lef/find-macro lef-lib cell-name)]
    {:cell-name cell-name
     :instance-name instance-name
     :width-sites (macro->site-width macro site-width-um)}))

(defn placed-cell->gdsii-elements
  "Given one `pnr.placement/place-cells` output cell
  (`{:cell-name :instance-name :x :y :orientation :row-idx}`) and its LEF
  macro (looked up via `lef/find-macro`), produce a vector of
  `pnr.gdsii/export-gdsii`-ready element maps: one `:kind :boundary`
  covering the macro's overall `:size` bounding box, plus one
  `:kind :boundary` per pin `:port` rect (on a metal-layer GDSII number
  via `layer-number`, falling back to 99). All geometry is translated to
  the cell's real placement offset: `:x` (site units) and `:row-idx` (row
  units) are converted to microns via `site-width-um`/`site-height-um`
  before the macro's local geometry (already in microns) is added on top
  and the result is scaled to GDSII database units.

  Returns nil if `cell-name` isn't found in `lef-lib`.

  SIMPLIFICATION, documented deliberately and not a silent bug:
  `:orientation` (R0/MX/MY/etc, standard-cell row-flip and rotation) is
  NOT applied to the geometry in this first pass -- only translation by
  the placed offset. A mirrored/rotated cell's boundary and pin rects are
  emitted at their un-mirrored, un-rotated local coordinates, just moved
  to the right place. Applying the orientation transform to the local
  geometry is left to a follow-up pass."
  [lef-lib placed-cell site-width-um site-height-um]
  (when-let [macro (lef/find-macro lef-lib (:cell-name placed-cell))]
    (let [ox-um (* (:x placed-cell) site-width-um)
          oy-um (* (:row-idx placed-cell) site-height-um)
          [w-um h-um] (:size macro)
          cell-boundary {:kind :boundary :layer 1 :datatype 0
                         :xy (closed-rect-dbu ox-um oy-um 0.0 0.0 w-um h-um)}
          pin-boundaries (for [pin (:pins macro)
                                port (:port pin)
                                :let [[x1 y1 x2 y2] (:rect port)]]
                           {:kind :boundary :layer (layer->number (:layer port)) :datatype 0
                            :xy (closed-rect-dbu ox-um oy-um x1 y1 x2 y2)})]
      (vec (cons cell-boundary pin-boundaries)))))

(defn design->gdsii-structure
  "Map `placed-cell->gdsii-elements` over all `placed-cells` (a
  `pnr.placement/place-cells` `:cells` seq) and flatten into one
  `pnr.gdsii/export-gdsii`-ready structure map `{:name :elements}`. Cells
  whose `:cell-name` isn't found in `lef-lib` contribute no elements
  (skipped, not an error) -- see `placed-cell->gdsii-elements`."
  [lef-lib placed-cells site-width-um site-height-um structure-name]
  {:name structure-name
   :elements (vec (mapcat #(placed-cell->gdsii-elements lef-lib % site-width-um site-height-um)
                           placed-cells))})
