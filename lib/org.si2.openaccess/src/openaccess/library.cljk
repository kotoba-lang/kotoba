(ns openaccess.library
  "Simplified OpenAccess Lib/Cell/View hierarchy.

  A library groups cells; each cell groups views keyed by view type
  (`:layout`/`:schematic`/`:symbol`); each view's `:content-ref` holds
  that view's design contents (see `openaccess.design`).

  This is a small, static, EDN-native model of the real OpenAccess
  object model (`oaLib`/`oaDesign`/`oaCellView`), not the OpenAccess
  C++ API and not a database (no persistence, no incremental save,
  no open-mode/lock semantics).

    library := {:name string? :cells [cell]}
    cell    := {:name string? :views [view]}
    view    := {:name string? :view-type (:layout|:schematic|:symbol)
                :content-ref design}")

(defn library
  "Construct a library named `name` containing `cells`."
  [name cells]
  {:name name :cells cells})

(defn cell
  "Construct a cell named `name` containing `views`."
  [name views]
  {:name name :views views})

(defn view
  "Construct a view named `name` of `view-type`
  (`:layout`/`:schematic`/`:symbol`) whose contents are `content-ref`
  (an `openaccess.design/design` map)."
  [name view-type content-ref]
  {:name name :view-type view-type :content-ref content-ref})

(defn find-cell
  "Look up the cell named `cell-name` in `lib`, or `nil` if `lib` has no
  such cell."
  [lib cell-name]
  (some #(when (= cell-name (:name %)) %) (:cells lib)))

(defn find-view
  "Look up the view of `view-type` (`:layout`/`:schematic`/`:symbol`)
  within `cell`, or `nil` if `cell` has no such view."
  [cell view-type]
  (some #(when (= view-type (:view-type %)) %) (:views cell)))

(defn find-cell-view
  "Convenience composition of `find-cell` + `find-view`: look up the
  `view-type` view of the cell named `cell-name` in `lib` directly,
  or `nil` if either lookup fails."
  [lib cell-name view-type]
  (some-> (find-cell lib cell-name) (find-view view-type)))
