(ns freeboard.render
  "Board → kami render-IR. Following kami-app-sip-clj's pattern: clj is the
   brain, browser/GPU execution belongs to host adapters over kami-engine-sdk-clj.
   For a flat infinite canvas we bake the viewport (pan/zoom) into screen-space
   quads (2D, kami-ui-gpu), z-sorted, with an identity ortho camera — so the
   renderer is a dumb executor of this draw-list. See ADR-2606280200.

   draw-list = {:clear [r g b a] :draws [draw …]}
   draw      = {:eid :kind :rect [sx sy sw sh] :z :fill :stroke
                (:text/runs | :image/blob | :shape/type | :ink :points)}"
  (:require [freeboard.board :as b]))

(def nintendo-cream
  "kami default clear color #f0ead6 (KAMI prohibits dark themes — fits a light
   Freeform-style canvas)."
  [0.94 0.917 0.839 1.0])

(defn cubic-bezier
  "Sample a cubic Bézier P0→P3 (control P1,P2) into `n`+1 points (incl. ends)."
  [[p0x p0y] [p1x p1y] [p2x p2y] [p3x p3y] n]
  (mapv (fn [i] (let [t (/ (double i) n) u (- 1.0 t)
                      a (* u u u) b (* 3 u u t) c (* 3 u t t) d (* t t t)]
                  [(+ (* a p0x) (* b p1x) (* c p2x) (* d p3x))
                   (+ (* a p0y) (* b p1y) (* c p2y) (* d p3y))]))
        (range (inc n))))

(defn connector-route
  "Smooth S-curve polyline between two screen points (horizontal tangents)."
  [[ax ay] [bx by]]
  (let [dx (* 0.5 (- bx ax))]
    (cubic-bezier [ax ay] [(+ ax dx) ay] [(- bx dx) by] [bx by] 16)))

(defn- item->draw [board vp it]
  (let [[sx sy] (b/world->screen vp [(:item/x it) (:item/y it)])
        z       (:zoom vp)
        base {:eid    (:item/id it)
              :kind   (:item/kind it)
              :rect   [sx sy (* (:item/w it) z) (* (:item/h it) z)]
              :z      (:item/z it)
              :fill   (:item/fill it)
              :stroke (:item/stroke it)}]
    (case (:item/kind it)
      :text  (assoc base :text/runs (:text/runs it))
      :image (assoc base :image/blob (:image/blob it) :image/texture (:image/texture it))
      :shape (assoc base :shape/type (:shape/type it :rect) :vector/points (:vector/points it))
      :ink   (assoc base :ink/polyline (mapv #(b/world->screen vp %) (:ink/points it []))
                    :ink/width (* (:ink/width it 2.0) z))
      :frame (assoc base :frame/title (:frame/title it))
      :connector (when-let [eps (b/connector-endpoints board it)]
                   (let [[a b'] (mapv #(b/world->screen vp %) eps)]
                     (assoc base :connector/polyline (connector-route a b'))))
      :group (assoc base :frame/title (:frame/title it) :group? true)
      base)))

(defn draw-list
  "Build a screen-space, z-sorted draw-list for the current viewport.
   Connectors resolve their endpoints from linked items; ink/connectors are
   polylines, everything else a rect."
  [board]
  (let [vp (:freeboard/viewport board)]
    {:clear nintendo-cream
     :viewport vp
     :draws (->> (b/items-z-asc board)
                 (map #(item->draw board vp %))
                 (remove nil?)                                 ; connectors with vanished endpoints → nil
                 vec)}))

;; ---- kami ECS adapter ------------------------------------------------------
;; A thin bridge to kami-engine-sdk-clj scene entities. Each draw → an entity
;; carrying the component attrs kami.render queries (`:kami/eid`,
;; `:transform/translation`, `:transform/scale`, `:mesh/asset`). Colour/text are
;; carried as material/atlas asset refs at integration time (see render.cljc in
;; kami-engine-sdk-clj). Kept data-only here so it's testable without the SDK.
(defn ->kami-entity [draw]
  (let [[sx sy sw sh] (:rect draw)]
    {:kami/eid               (:eid draw)
     :transform/translation  [sx sy (* 0.001 (:z draw))]      ; small z for layering
     :transform/scale        [sw sh 1.0]
     :mesh/asset             (case (:kind draw) :text "kami:text-quad" :image "kami:image-quad" "kami:unit-quad")
     :freeboard/draw         draw}))                           ; carry the draw for asset/material resolution

(defn kami-scene [board]
  (mapv ->kami-entity (:draws (draw-list board))))
