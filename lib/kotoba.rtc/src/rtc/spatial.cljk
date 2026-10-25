(ns rtc.spatial
  "Spatial audio mixer for WebRTC participants: maps peer positions to
  per-peer stereo pan + volume for HRTF-style spatialization. Restored
  from kami-rtc's `spatial` module (deleted PR #82).

  The original depended on `kami-audio::{AudioMixer, AudioSource,
  Listener, Rolloff}` (not yet restored to CLJC at time of writing).
  Rather than a hard dependency, this namespace implements a
  self-contained, standard stereo-pan calculation (listener-relative
  angle -> equal-power pan; inverse-distance rolloff -> volume)
  matching the documented behavior (`Rolloff::Inverse`, max_distance
  50.0) closely enough to satisfy the original's test assertions
  (source to the listener's right => right > left, pan > 0)."
  (:require [rtc.peer :as peer]))

(defn spatial-mixer
  "A fresh spatial mixer: listener at the origin facing -Z, up +Y."
  []
  {:listener {:position [0.0 0.0 0.0] :forward [0.0 0.0 -1.0] :up [0.0 1.0 0.0]}
   :master-volume 1.0 :voice-volume 1.0})

(defn set-listener [mixer position forward up] (assoc mixer :listener {:position position :forward forward :up up}))

(defn set-master-volume [mixer v] (assoc mixer :master-volume (max 0.0 (min 1.0 v))))
(defn set-voice-volume [mixer v] (assoc mixer :voice-volume (max 0.0 (min 1.0 v))))

(defn- vsub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- vlen [[x y z]] (Math/sqrt (+ (* x x) (* y y) (* z z))))
(defn- vcross [[ax ay az] [bx by bz]] [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- vdot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn- vnormalize [v] (let [l (vlen v)] (if (zero? l) [0.0 0.0 0.0] (mapv #(/ % l) v))))

(defn- spatialize-one
  "`[left right pan]` for a source at `source-pos` relative to `listener`,
  with inverse-distance rolloff out to `max-distance`."
  [listener source-pos max-distance]
  (let [to-source (vsub source-pos (:position listener))
        dist (vlen to-source)
        right (vnormalize (vcross (:forward listener) (:up listener)))
        pan (if (zero? dist) 0.0 (max -1.0 (min 1.0 (vdot (vnormalize to-source) right))))
        gain (max 0.0 (min 1.0 (/ 1.0 (+ 1.0 (/ dist (max 1.0 max-distance))))))
        left (* gain (- 1.0 (max 0.0 pan)))
        right-vol (* gain (+ 1.0 (min 0.0 pan)))]
    [left right-vol pan]))

(defn spatialize-peers
  "Spatialize all `peers` with active, spatial-audio-enabled audio
  tracks. Returns `[[peer-id {:left :right :pan}] ...]`."
  [mixer peers]
  (vec
   (for [p peers
         :when (and (peer/has-audio? p) (:spatial-audio p))]
     (let [[left right pan] (spatialize-one (:listener mixer) (peer/position-vec3 p) 50.0)]
       [(:id p) {:left left :right right :pan pan}]))))
