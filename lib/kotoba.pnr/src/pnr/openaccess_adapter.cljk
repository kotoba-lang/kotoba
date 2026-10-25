(ns pnr.openaccess-adapter
  "Bridges org-si2-lef (LEF physical cell library) and pnr.placement output
  into org-si2-openaccess (a simplified Si2/OpenAccess Lib/Cell/View
  hierarchy with real 2D instance-transform math). `pnr.lef-adapter` and
  `pnr.def-adapter` already export a placement as GDSII (via
  `pnr.gdsii`) and DEF (via `org-si2-def`) respectively; this namespace is a
  third export path -- an OpenAccess-shaped design (a library of Cells/Views
  built from LEF macros, plus a top-level View whose contents instantiate
  those Cells at each placed cell's location/orientation) -- and it is the
  first of the three to exercise a *hierarchical instance-transform*: every
  placed cell becomes an `openaccess.design/instance`, and flattening that
  design (`openaccess.query/flatten-instances`) resolves each instance's
  local pin/OBS geometry into the top design's coordinate system via
  `openaccess.design/instance-transform-point`.

  ORIENTATION, correctly applied (unlike `pnr.lef-adapter`): `pnr.placement`
  places cells using LEF/DEF's own orientation vocabulary
  (`pnr.placement/orientations` => `:n :s :e :w :fn :fs :fe :fw`), which is
  NOT the vocabulary `openaccess.design` uses for the same 8 Manhattan
  orientations (`:R0 :R90 :R180 :R270 :MX :MY :MXR90 :MYR90`).
  `pnr.lef-adapter/placed-cell->gdsii-elements` sidesteps this mismatch by
  documenting, deliberately, that it does NOT apply `:orientation` to
  geometry at all (translation only) -- a real gap for any placement
  containing a non-`:n` cell. This namespace closes that gap:
  `pnr-orientation->oa-orientation` translates every placed cell's
  orientation into `openaccess.design`'s vocabulary before handing it to
  `openaccess.design/instance-transform-point` (via
  `openaccess.query/flatten-instances`), which implements the correct
  rotation/mirror matrix for all 8 orientations. So `design->flat-shapes`'s
  output IS geometrically correct for mirrored/rotated cells, where
  `pnr.lef-adapter`'s GDSII boundaries are not.

  SITE/ROW UNITS, same simplification `pnr.lef-adapter`/`pnr.def-adapter`
  already document: a `pnr.placement/place-cells` output cell's `:x` is in
  whatever unit the placement row's `:site-width` was defined in (a real
  micron pitch, or a placeholder integer-site convention, e.g. `1.0` --
  `pnr.placement` itself has no opinion), and `:row-idx` is a ROW INDEX
  (an integer counter for which row the cell landed in), not a
  y-coordinate of any unit. `placement->oa-design` (below), like
  `pnr.def-adapter/placed-cell->def-component`'s single-arity, no-scale
  default, passes `:x`/`:row-idx` straight through UNSCALED into the
  instance transform's `:offset` -- it does not claim these are real
  microns, and does not invent a `site-width-um`/`site-height-um` scaling
  step of its own (a caller who needs real-micron offsets can scale
  `:x`/`:row-idx` before calling this, the same way `pnr.lef-adapter`/
  `pnr.def-adapter`'s callers do)."
  (:require [openaccess.library :as oa-lib]
            [openaccess.shape :as oa-shape]
            [openaccess.design :as oa-design]
            [openaccess.query :as oa-query]
            [lef.core :as lef]))

(def pnr-orientation->oa-orientation
  "`pnr.placement`'s LEF/DEF-style orientation keyword (see
  `pnr.placement/orientations`: `:n :s :e :w :fn :fs :fe :fw`) ->
  `openaccess.design`'s orientation keyword for the same 8 Manhattan
  orientations (`:R0 :R90 :R180 :R270 :MX :MY :MXR90 :MYR90`).

  Table per the official LEF/DEF-to-OpenAccess correspondence published in
  the LEF/DEF 5.7 Language Reference ('Specifying Orientation', DEF Syntax
  chapter): N->R0, S->R180, W->R90, E->R270, FN->MY, FS->MX, FW->MX90
  (`:MXR90` here), FE->MY90 (`:MYR90` here)."
  {:n :R0, :s :R180, :w :R90, :e :R270
   :fn :MY, :fs :MX, :fw :MXR90, :fe :MYR90})

(defn- lef-rect->oa-rect
  "Convert one LEF `{:layer :rect [x1 y1 x2 y2]}` map (a pin PORT rect or an
  OBS rect, `lef.core/parse-lef`'s shape for both) into an
  `openaccess.shape/rect`. The LEF layer name (a string, e.g. `\"metal1\"`)
  becomes an OA layer keyword via `keyword` -- `openaccess.shape` has no
  metal-layer-name -> GDSII-layer-number concept of its own (that's
  `pnr.lef-adapter/layer-number`'s job for the GDSII path only), it just
  wants *a* layer keyword to filter/group shapes by."
  [{:keys [layer rect]}]
  (oa-shape/rect (keyword layer) rect))

(defn lef-macro->oa-cell
  "Convert one LEF macro (`lef.core/parse-lef` macro map:
  `{:name :size [w h] :pins [{:port [{:layer :rect} ...]} ...] :obs [{:layer
  :rect} ...]}`) into an `openaccess.library`-shaped Cell
  (`openaccess.library/cell`) named `(:name lef-macro)`, with a single
  `:layout` View (`openaccess.library/view`) whose contents
  (`openaccess.design/design`) hold one `openaccess.shape/rect` per pin
  PORT rect (in macro-pin order) followed by one rect per OBS rect, and NO
  `:instances` -- a LEF macro is leaf physical geometry (a standard cell's
  abstract view): it has no sub-instances of its own, only the pin/OBS
  shapes `lef.core/parse-lef` already extracted."
  [lef-macro]
  (let [pin-rects (for [pin (:pins lef-macro)
                        port (:port pin)]
                    (lef-rect->oa-rect port))
        obs-rects (map lef-rect->oa-rect (:obs lef-macro))
        shapes (vec (concat pin-rects obs-rects))]
    (oa-lib/cell (:name lef-macro)
                 [(oa-lib/view "layout" :layout (oa-design/design shapes []))])))

(defn lef-library->oa-library
  "Convert a full parsed LEF library (`lef.core/parse-lef`'s output,
  `{:macros [...]}`) into a single `openaccess.library`-shaped library map
  named `lib-name`, mapping `lef-macro->oa-cell` over every macro."
  [lib-name lef-lib]
  (oa-lib/library lib-name (mapv lef-macro->oa-cell (:macros lef-lib))))

(defn placement->oa-design
  "Convert a `pnr.placement/place-cells` placement (`{:cells [{:cell-name
  :instance-name :x :y :orientation :row-idx} ...] :rows [...]}`) into an
  `openaccess.design`-shaped top-level View-contents map (`design-name` is
  accepted for API symmetry with `pnr.lef-adapter/design->gdsii-structure`
  and `pnr.def-adapter/placement->def-design` -- both of which take a
  design/structure name -- but is otherwise unused here: unlike DEF's
  DESIGN header or a GDSII structure record, `openaccess.design`'s
  View-contents map has no `:name` field of its own; a caller who wants
  `design-name` attached names the *View* with it, e.g. `(oa-lib/view
  design-name :layout (placement->oa-design design-name placement lib))`).

  `:shapes` is always `[]` -- nothing is drawn directly at the top level,
  every placed cell is instead an `openaccess.design/instance` of that
  cell's `:layout` view in `oa-library`.

  Each placed cell becomes one instance:
  `:cell-ref` is `(:cell-name cell)`, `:view-ref` is always `:layout`, and
  `:transform` is `{:offset [(:x cell) (:row-idx cell)] :orientation
  (pnr-orientation->oa-orientation (:orientation cell))}` -- see this ns's
  docstring for why the orientation keyword is translated (the two
  namespaces use different vocabularies for the same 8 orientations) and
  why the offset is passed through in `:x`/`:row-idx`'s own units, unscaled
  (site/row units, not necessarily real microns).

  Placed cells whose `:cell-name` has no `:layout` view in `oa-library`
  (`openaccess.library/find-cell-view`) are skipped -- no instance is
  emitted for them, matching `pnr.lef-adapter/design->gdsii-structure`'s
  convention of silently skipping (not erroring on) cells the library
  can't resolve."
  [_design-name placement oa-library]
  (let [resolved (filter #(oa-lib/find-cell-view oa-library (:cell-name %) :layout)
                         (:cells placement))]
    (oa-design/design
     []
     (mapv (fn [placed-cell]
             (oa-design/instance (:cell-name placed-cell)
                                  :layout
                                  [(:x placed-cell) (:row-idx placed-cell)]
                                  (pnr-orientation->oa-orientation (:orientation placed-cell))))
           resolved))))

(defn design->flat-shapes
  "Convenience wrapper over `openaccess.query/flatten-instances`: fully
  flatten `design`'s (one level of) instances against `oa-library`,
  returning the whole placed design's pin/OBS geometry with every
  instance's transform already resolved into the top design's coordinate
  system -- real, 2D-transformed geometry for every placed cell, computed
  via `openaccess.design/instance-transform-point`'s actual 8-orientation
  matrix rather than translation alone.

  THIS is the payoff over `pnr.lef-adapter`'s GDSII path (see this ns's
  docstring): a cell placed at a non-`:n` (non-R0) orientation has its
  pin/OBS rects correctly rotated/mirrored here, where
  `pnr.lef-adapter/placed-cell->gdsii-elements` documents that it does
  NOT apply orientation to geometry at all."
  [oa-library design]
  (oa-query/flatten-instances oa-library design))
