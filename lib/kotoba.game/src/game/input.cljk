(ns game.input
  "Input system: keyboard -> movement velocity -> physics body.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/input.rs`.
  Vec3 is represented as a plain 3-vector `[x y z]`.")

;; InputState: {:forward? :backward? :left? :right? :jump? :interact? :chat?}
;; PlayerController: {:move-speed :jump-impulse}

(defn input-state-default
  "All-false input state (polled from keyboard events)."
  []
  {:forward? false
   :backward? false
   :left? false
   :right? false
   :jump? false
   :interact? false
   :chat? false})

(defn player-controller-default
  []
  {:move-speed 5.0
   :jump-impulse 8.0})

;; -----------------------------------------------------------------------
;; Local Vec3 math (no hard dep on any other cluster's vector namespace).
;; -----------------------------------------------------------------------

(defn- v3-length-squared [[x y z]]
  (+ (* x x) (* y y) (* z z)))

(defn- v3-normalize [[x y z :as v]]
  (let [len (Math/sqrt (v3-length-squared v))]
    (if (zero? len)
      [0.0 0.0 0.0]
      [(/ x len) (/ y len) (/ z len)])))

(defn- v3-scale [[x y z] s]
  [(* x s) (* y s) (* z s)])

(defn movement-velocity
  "Compute movement velocity vector from `input` state + `camera-yaw`
  (radians), scaled by `controller`'s move-speed."
  [controller input camera-yaw]
  (let [dz (+ (if (:forward? input) -1.0 0.0) (if (:backward? input) 1.0 0.0))
        dx (+ (if (:left? input) -1.0 0.0) (if (:right? input) 1.0 0.0))
        dir [dx 0.0 dz]]
    (if (< (v3-length-squared dir) 0.001)
      [0.0 0.0 0.0]
      (let [[dx' _ dz'] (v3-normalize dir)
            cos (Math/cos camera-yaw)
            sin (Math/sin camera-yaw)
            rotated [(- (* dx' cos) (* dz' sin))
                     0.0
                     (+ (* dx' sin) (* dz' cos))]]
        (v3-scale rotated (:move-speed controller))))))

;; -----------------------------------------------------------------------
;; KNP Channel 0 position (de)serialization: little-endian f32 x,y,z.
;; -----------------------------------------------------------------------

#?(:clj
   (defn position->bytes
     "Serialize a [x y z] Vec3 position as 12 little-endian f32 bytes."
     [[x y z]]
     (let [buf (java.nio.ByteBuffer/allocate 12)]
       (.order buf java.nio.ByteOrder/LITTLE_ENDIAN)
       (.putFloat buf (float x))
       (.putFloat buf (float y))
       (.putFloat buf (float z))
       (.array buf)))
   :cljs
   (defn position->bytes
     [[x y z]]
     (let [buf (js/ArrayBuffer. 12)
           view (js/DataView. buf)]
       (.setFloat32 view 0 x true)
       (.setFloat32 view 4 y true)
       (.setFloat32 view 8 z true)
       (js/Uint8Array. buf))))

#?(:clj
   (defn bytes->position
     "Deserialize a Vec3 position from 12+ little-endian f32 bytes, or nil
     if too short."
     [^bytes data]
     (when (>= (alength data) 12)
       (let [buf (java.nio.ByteBuffer/wrap data)]
         (.order buf java.nio.ByteOrder/LITTLE_ENDIAN)
         [(.getFloat buf 0) (.getFloat buf 4) (.getFloat buf 8)])))
   :cljs
   (defn bytes->position
     [data]
     (when (>= (.-length data) 12)
       (let [view (js/DataView. (.-buffer data) (.-byteOffset data) (.-byteLength data))]
         [(.getFloat32 view 0 true) (.getFloat32 view 4 true) (.getFloat32 view 8 true)]))))
