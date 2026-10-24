(ns engineer-render.viewport
  "2D engineering viewport: pan/zoom + screen<->world coordinate transforms.
  Restored from kami-eng-render's `EngViewport` (deleted PR #82). Points are
  `[x y]` 2-vectors (glam::Vec2 in the original).

  The transforms delegate to kotoba-lang/canvaskit (UIScrollView semantics,
  ADR-2607071130); this ns keeps the original centered-origin viewport shape
  `{:center :zoom :rotation :width :height}` (offset = center*zoom - bounds/2)."
  (:require [canvaskit.scroll-view :as cksv]))

(defn viewport
  "A fresh viewport at `[width height]` pixels, centered at origin, zoom 1."
  [width height]
  {:center [0.0 0.0] :zoom 1.0 :rotation 0.0 :width width :height height})

;; The original EngViewport has no zoom clamp — keep canvaskit's clamp fully open.
(def ^:private no-clamp {:minimum-zoom-scale 0.0 :maximum-zoom-scale ##Inf})

(defn- ->scroll-view [{:keys [center zoom width height]}]
  (let [[cx cy] center]
    (cksv/scroll-view
     (assoc no-clamp
            :bounds [width height]
            :zoom-scale zoom
            :content-offset [(- (* cx zoom) (/ width 2.0))
                             (- (* cy zoom) (/ height 2.0))]))))

(defn- merge-scroll-view [vp {:keys [content-offset zoom-scale bounds]}]
  (let [[ox oy] content-offset
        [w h]   bounds]
    (assoc vp :zoom zoom-scale
           :center [(/ (+ ox (/ w 2.0)) zoom-scale)
                    (/ (+ oy (/ h 2.0)) zoom-scale)])))

(defn screen->world
  "Convert screen-space `[sx sy]` to world-space, honoring the viewport's
  center/zoom (rotation is not yet applied — matches the original, which
  also ignored `:rotation` in this transform)."
  [vp screen-pt]
  (cksv/convert-point-from-view (->scroll-view vp) screen-pt))

(defn world->screen
  "Convert world-space `[wx wy]` to screen-space, the inverse of `screen->world`."
  [vp world-pt]
  (cksv/convert-point-to-view (->scroll-view vp) world-pt))

(defn zoom-to-fit
  "Recenter + rezoom the viewport so the world-space bounding box `[min max]`
  fits with a 10% margin (0.9 fill factor, matching the original)."
  [vp [minx miny] [maxx maxy]]
  (let [cx  (/ (+ minx maxx) 2.0)
        cy  (/ (+ miny maxy) 2.0)
        ;; 10% margin = aspect-fit a bbox inflated by 1/0.9 around the same
        ;; center, so zoom-to-rect yields exactly 0.9 * min(w/ex, h/ey).
        ex' (/ (- maxx minx) 0.9)
        ey' (/ (- maxy miny) 0.9)]
    (merge-scroll-view
     vp (cksv/zoom-to-rect (->scroll-view vp)
                           [(- cx (/ ex' 2.0)) (- cy (/ ey' 2.0)) ex' ey']))))
