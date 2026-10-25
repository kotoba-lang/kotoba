(ns kotoba.live.camera
  "Camera rig framing the performer (`:dance/camera`). The eye sits at the
  live performer position + `:offset`; the look target at performer +
  `:look`. So the camera follows the dancer, but the rig (distance, height,
  fov) is authored as data. An optional `:shots` list keys offsets to bars
  for a camera-work choreography (wide -> close -> side ...), dollied with a
  smoothstep ease."
  (:require [kotoba.live.vec3 :as v3]))

(defn default-rig []
  {:offset [0.0 3.0 8.0] :look [0.0 1.0 0.0] :fov 0.9 :shots []})

(defn shot [at-bar offset look] {:at-bar at-bar :offset offset :look look})

(defn- smoothstep [t] (* t t (- 3.0 (* 2.0 t))))

(defn framing-at
  "`[offset look]` at a continuous bar position. With no `:shots` this is the
  static rig; otherwise the active shot dollies toward the next one."
  [rig bar]
  (let [shots (:shots rig)]
    (if (empty? shots)
      [(:offset rig) (:look rig)]
      (let [i (loop [k 0 best 0]
                (if (>= k (count shots))
                  best
                  (recur (inc k) (if (<= (:at-bar (nth shots k)) bar) k best))))
            a (nth shots i)]
        (if (< (inc i) (count shots))
          (let [b (nth shots (inc i))
                span (max 1e-3 (- (:at-bar b) (:at-bar a)))
                t (smoothstep (max 0.0 (min 1.0 (/ (- bar (:at-bar a)) span))))]
            [(v3/lerp (:offset a) (:offset b) t) (v3/lerp (:look a) (:look b) t)])
          [(:offset a) (:look a)])))))
