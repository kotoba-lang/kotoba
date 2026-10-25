(ns cnc-toolpath.toolpath
  "Toolpath generation: CAM operations, segment types, and job
  execution. Restored from kami-cam's `toolpath` module (deleted PR
  #82)."
  (:require [cnc-toolpath.tool :as tool]))

(def pocket-strategies #{:zigzag :spiral :trochoidal-peel})
(def surface-strategies #{:raster :spiral :waterline :pencil})
(def contour-sides #{:inside :outside :on-line})
(def segment-types #{:rapid :linear :arc-cw :arc-ccw})

;; CamOperation constructors — each returns a tagged map `{:op <kind> ...}`.

(defn face-mill-op [{:keys [tool-id depth-of-cut stepover feed-rate spindle-rpm]}]
  {:op :face-mill :tool-id tool-id :depth-of-cut depth-of-cut :stepover stepover
   :feed-rate feed-rate :spindle-rpm spindle-rpm})

(defn pocket-op [{:keys [tool-id depth stepover strategy feed-rate spindle-rpm pocket-min pocket-max]}]
  {:op :pocket :tool-id tool-id :depth depth :stepover stepover :strategy strategy
   :feed-rate feed-rate :spindle-rpm spindle-rpm :pocket-min pocket-min :pocket-max pocket-max})

(defn contour-op [{:keys [tool-id depth side feed-rate spindle-rpm]}]
  {:op :contour :tool-id tool-id :depth depth :side side :feed-rate feed-rate :spindle-rpm spindle-rpm})

(defn drill-op [{:keys [tool-id depth peck-depth feed-rate spindle-rpm holes]}]
  {:op :drill :tool-id tool-id :depth depth :peck-depth peck-depth
   :feed-rate feed-rate :spindle-rpm spindle-rpm :holes (vec holes)})

(defn surface-3d-op [{:keys [tool-id stepover strategy feed-rate spindle-rpm]}]
  {:op :surface-3d :tool-id tool-id :stepover stepover :strategy strategy
   :feed-rate feed-rate :spindle-rpm spindle-rpm})

(defn turn-op [{:keys [tool-id depth-of-cut feed-rate spindle-rpm]}]
  {:op :turn :tool-id tool-id :depth-of-cut depth-of-cut :feed-rate feed-rate :spindle-rpm spindle-rpm})

(defn toolpath-segment [{:keys [segment-type start end feed-rate center tool-id]}]
  {:segment-type segment-type :start start :end end :feed-rate feed-rate :center center :tool-id tool-id})

(defn cam-job
  [stock tool-library]
  {:stock stock :operations [] :tool-library tool-library :safe-height 5.0})

(defn add-operation [job op] (update job :operations conj op))

(defn- vsub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- vlen [[x y z]] (Math/sqrt (+ (* x x) (* y y) (* z z))))
(defn- last-end [segments] (if (seq segments) (:end (peek segments)) [0.0 0.0 0.0]))

(defn- generate-pocket-segments [job op segments0]
  (let [{:keys [tool-id depth stepover feed-rate pocket-min pocket-max]} op
        [pmx pmy pmz] pocket-min
        [pXx pXy _pXz] pocket-max
        t (tool/get-tool (:tool-library job) tool-id)
        tool-radius (if t (/ (:diameter t) 2.0) 0.0)
        effective-stepover (if (> stepover 0.0) stepover tool-radius)
        x-min (+ pmx tool-radius) x-max (- pXx tool-radius)
        y-min (+ pmy tool-radius) y-max (- pXy tool-radius)
        z-top pmz
        z-bottom (- pmz depth)
        safe-z (+ z-top (:safe-height job))
        layer-doc (min effective-stepover depth)
        num-layers (long (Math/ceil (/ depth layer-doc)))]
    (reduce
     (fn [segments layer]
       (let [z (max z-bottom (- z-top (* (+ layer 1.0) layer-doc)))
             first-start [x-min y-min safe-z]
             segments (if (seq segments)
                        (conj segments (toolpath-segment
                                        {:segment-type :rapid :start (last-end segments)
                                         :end [x-min y-min safe-z] :feed-rate 0.0 :center nil :tool-id tool-id}))
                        segments)
             segments (conj segments (toolpath-segment
                                       {:segment-type :rapid :start first-start
                                        :end [x-min y-min z] :feed-rate 0.0 :center nil :tool-id tool-id}))
             segments
             (loop [segments segments y y-min forward true]
               (if (> y y-max)
                 segments
                 (let [[sx ex] (if forward [x-min x-max] [x-max x-min])
                       start [sx y z] end-pt [ex y z]
                       prev (last-end segments)
                       segments (if (> (vlen (vsub prev start)) 1e-6)
                                  (conj segments (toolpath-segment
                                                  {:segment-type :rapid :start prev :end start
                                                   :feed-rate 0.0 :center nil :tool-id tool-id}))
                                  segments)
                       segments (conj segments (toolpath-segment
                                                 {:segment-type :linear :start start :end end-pt
                                                  :feed-rate feed-rate :center nil :tool-id tool-id}))]
                   (recur segments (+ y effective-stepover) (not forward)))))
             prev (last-end segments)
             [prev-x prev-y _] prev
             segments (conj segments (toolpath-segment
                                       {:segment-type :rapid :start prev :end [prev-x prev-y safe-z]
                                        :feed-rate 0.0 :center nil :tool-id tool-id}))]
         segments))
     segments0
     (range num-layers))))

(defn- generate-drill-segments [job op segments0]
  (let [{:keys [tool-id depth peck-depth feed-rate holes]} op
        safe-z (:safe-height job)]
    (reduce
     (fn [segments hole]
       (let [[hx hy hz] hole
             top [hx hy safe-z]
             prev (last-end segments)
             segments (conj segments (toolpath-segment
                                       {:segment-type :rapid :start prev :end top
                                        :feed-rate 0.0 :center nil :tool-id tool-id}))
             z-bottom (- hz depth)]
         (loop [segments segments z hz]
           (if (<= z z-bottom)
             segments
             (let [target-z (max z-bottom (- z peck-depth))
                   segments (conj segments (toolpath-segment
                                             {:segment-type :linear :start [hx hy z] :end [hx hy target-z]
                                              :feed-rate feed-rate :center nil :tool-id tool-id}))
                   segments (conj segments (toolpath-segment
                                             {:segment-type :rapid :start [hx hy target-z] :end top
                                              :feed-rate 0.0 :center nil :tool-id tool-id}))]
               (recur segments target-z))))))
     segments0
     holes)))

(defn generate-toolpath
  "Generate toolpath segments for all operations in `job`, in order.
  Currently implements zigzag pocket and peck-drill cycles; other
  operations produce placeholder rapid moves to the tool-change point
  so the G-code structure is valid."
  [job]
  (reduce
   (fn [segments op]
     (case (:op op)
       :pocket (generate-pocket-segments job op segments)
       :drill (generate-drill-segments job op segments)
       (:face-mill :contour :surface-3d :turn)
       (conj segments (toolpath-segment
                        {:segment-type :rapid :start (last-end segments)
                         :end [0.0 0.0 (:safe-height job)] :feed-rate 0.0 :center nil :tool-id (:tool-id op)}))))
   []
   (:operations job)))
