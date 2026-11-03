(ns freeboard.import
  "Import a kasane :kasane/doc (any of PSD/PDF/AI/PNG/SVG/Sketch/… normalized by
   kasane.normalize) onto a freeboard board: drop the parsed document at a world
   point as placed items. Decoupled from kasane itself — takes the already-
   normalized doc map — so it stays pure/testable. See ADR-2606280200."
  (:require [freeboard.board :as b]))

(defn- node->item
  "Map a kasane :node → a freeboard item, offset to drop point (ox,oy)."
  [ox oy node]
  (let [[nx ny nw nh] (:node/bbox node [0 0 100 40])
        base {:item/x (+ ox nx) :item/y (+ oy ny)
              :item/w (max 1.0 nw) :item/h (max 1.0 nh)}]
    (case (:node/kind node)
      :text     (assoc base :item/kind :text  :text/runs (:text/runs node [{:text (:node/name node "")}]))
      :raster   (assoc base :item/kind :image :image/blob (:raster/blob node))
      :artboard (assoc base :item/kind :frame :frame/title (:node/name node "Artboard"))
      :page     (assoc base :item/kind :frame :frame/title (str "Page " (:pdf.page/index node "")))
      :vector   (assoc base :item/kind :shape :shape/type :rect
                       :item/fill (:node/fill node) :vector/points (:vector/points node))
      ;; default → a frame box carrying the kind label
      (assoc base :item/kind :frame :frame/title (name (or (:node/kind node) :group))))))

(defn drop-doc
  "Place a kasane doc's top-level nodes onto `board` at world point [ox oy].
   Returns the updated board. A wrapping frame named by the source format holds
   the canvas dimensions."
  [board {:keys [:kasane/format :kasane/canvas :kasane/nodes] :as _doc} [ox oy]]
  (let [{:keys [width height]} canvas
        framed (b/add-item board {:item/kind :frame
                                  :item/x ox :item/y oy
                                  :item/w (max 1.0 (or width 200))
                                  :item/h (max 1.0 (or height 200))
                                  :frame/title (name (or format :import))})]
    (reduce (fn [bd n] (b/add-item bd (node->item ox oy n))) framed nodes)))

(defn doc->items
  "Pure: kasane doc → seq of freeboard items at [ox oy] (no board)."
  [{:keys [:kasane/nodes]} [ox oy]]
  (mapv #(node->item ox oy %) nodes))
