(ns kotoba.ros.msgs
  "Standard ROS 2 message shapes -- pure EDN maps in, full CDR wire bytes
  (including the encapsulation header) out, and back.

  Exactly the messages a teleop bridge or a governed swarm-choreography
  bridge need, no more: `builtin_interfaces/Time`, `std_msgs/Header`,
  `std_msgs/Bool`, `geometry_msgs/Vector3`, `geometry_msgs/Twist`,
  `geometry_msgs/TwistStamped`, `geometry_msgs/Point`,
  `geometry_msgs/Quaternion`, `geometry_msgs/Pose`,
  `geometry_msgs/PoseStamped`, `sensor_msgs/Joy`.

  Field names match real ROS 2 message definitions verbatim (including
  `:frame_id`'s underscore) -- a JSON bridge (e.g. rosbridge_suite, see
  `kotoba.ros.rosbridge`) mirrors these keys as-is, so any deviation here
  would silently break interop with a live ROS 2 system.

  Every `encode-*` composes `kotoba.ros.cdr` primitives to build a message's
  body, wrapped in `cdr/encapsulate`; every `decode-*` mirrors it with
  `cdr/de-encapsulate`. Nested shapes (e.g. `Twist`'s two `Vector3`s,
  `TwistStamped`'s `Header`) are built from private `write-*`/`read-*`
  helpers that do NOT add their own encapsulation header -- only the
  outermost message gets one, matching how CDR nests real ROS 2 messages
  (a `Header` inside a `TwistStamped` is not itself re-encapsulated).

  Pure data in, pure data out: no network sockets, no device I/O, no
  filesystem I/O. Portable `.cljc`."
  (:refer-clojure :exclude [read-string])
  (:require [kotoba.ros.cdr :as cdr]))

;; ---------------------------------------------------------------------------
;; builtin_interfaces/Time -- {:sec <int32> :nanosec <uint32>}
;; ---------------------------------------------------------------------------

(defn- write-time [w t]
  (-> w (cdr/write-i32 (:sec t)) (cdr/write-u32 (:nanosec t))))

(defn- read-time [r]
  (let [[sec r] (cdr/read-i32 r)
        [nanosec r] (cdr/read-u32 r)]
    [{:sec sec :nanosec nanosec} r]))

(defn encode-time
  "builtin_interfaces/Time -> full CDR bytes (encapsulation header + body)."
  [t]
  (:bytes (write-time (cdr/encapsulate (cdr/writer)) t)))

(defn decode-time
  "Full CDR bytes -> builtin_interfaces/Time EDN map."
  [bytes]
  (first (read-time (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; std_msgs/Header -- {:stamp <Time> :frame_id <string>}
;; ---------------------------------------------------------------------------

(defn- write-header [w h]
  (-> w (write-time (:stamp h)) (cdr/write-string (:frame_id h))))

(defn- read-header [r]
  (let [[stamp r] (read-time r)
        [frame_id r] (cdr/read-string r)]
    [{:stamp stamp :frame_id frame_id} r]))

(defn encode-header
  "std_msgs/Header -> full CDR bytes."
  [h]
  (:bytes (write-header (cdr/encapsulate (cdr/writer)) h)))

(defn decode-header
  "Full CDR bytes -> std_msgs/Header EDN map."
  [bytes]
  (first (read-header (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; std_msgs/Bool -- {:data <bool>}. bool = 1 unaligned byte, 0 or 1.
;; ---------------------------------------------------------------------------

(defn- write-bool-field [w b] (cdr/write-u8 w (if b 1 0)))

(defn- read-bool-field [r]
  (let [[v r] (cdr/read-u8 r)] [(not (zero? v)) r]))

(defn encode-bool
  "std_msgs/Bool -> full CDR bytes."
  [m]
  (:bytes (write-bool-field (cdr/encapsulate (cdr/writer)) (:data m))))

(defn decode-bool
  "Full CDR bytes -> std_msgs/Bool EDN map."
  [bytes]
  (let [[data _r] (read-bool-field (cdr/de-encapsulate (cdr/reader bytes)))]
    {:data data}))

;; ---------------------------------------------------------------------------
;; geometry_msgs/Vector3 -- {:x <float64> :y <float64> :z <float64>}
;; ---------------------------------------------------------------------------

(defn- write-vector3 [w v]
  (-> w (cdr/write-f64 (:x v)) (cdr/write-f64 (:y v)) (cdr/write-f64 (:z v))))

(defn- read-vector3 [r]
  (let [[x r] (cdr/read-f64 r)
        [y r] (cdr/read-f64 r)
        [z r] (cdr/read-f64 r)]
    [{:x x :y y :z z} r]))

(defn encode-vector3
  "geometry_msgs/Vector3 -> full CDR bytes."
  [v]
  (:bytes (write-vector3 (cdr/encapsulate (cdr/writer)) v)))

(defn decode-vector3
  "Full CDR bytes -> geometry_msgs/Vector3 EDN map."
  [bytes]
  (first (read-vector3 (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; geometry_msgs/Twist -- {:linear <Vector3> :angular <Vector3>}
;; ---------------------------------------------------------------------------

(defn- write-twist [w t]
  (-> w (write-vector3 (:linear t)) (write-vector3 (:angular t))))

(defn- read-twist [r]
  (let [[linear r] (read-vector3 r)
        [angular r] (read-vector3 r)]
    [{:linear linear :angular angular} r]))

(defn encode-twist
  "geometry_msgs/Twist -> full CDR bytes."
  [t]
  (:bytes (write-twist (cdr/encapsulate (cdr/writer)) t)))

(defn decode-twist
  "Full CDR bytes -> geometry_msgs/Twist EDN map."
  [bytes]
  (first (read-twist (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; geometry_msgs/TwistStamped -- {:header <Header> :twist <Twist>}
;; ---------------------------------------------------------------------------

(defn- write-twist-stamped [w ts]
  (-> w (write-header (:header ts)) (write-twist (:twist ts))))

(defn- read-twist-stamped [r]
  (let [[header r] (read-header r)
        [twist r] (read-twist r)]
    [{:header header :twist twist} r]))

(defn encode-twist-stamped
  "geometry_msgs/TwistStamped -> full CDR bytes."
  [ts]
  (:bytes (write-twist-stamped (cdr/encapsulate (cdr/writer)) ts)))

(defn decode-twist-stamped
  "Full CDR bytes -> geometry_msgs/TwistStamped EDN map."
  [bytes]
  (first (read-twist-stamped (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; geometry_msgs/Point -- {:x <float64> :y <float64> :z <float64>}
;; Wire-identical to Vector3 (three float64 fields) but semantically a
;; position rather than a free vector -- ROS 2 keeps them as distinct
;; message types, so this library does too, with its own write/read pair
;; rather than aliasing Vector3's.
;; ---------------------------------------------------------------------------

(defn- write-point [w p]
  (-> w (cdr/write-f64 (:x p)) (cdr/write-f64 (:y p)) (cdr/write-f64 (:z p))))

(defn- read-point [r]
  (let [[x r] (cdr/read-f64 r)
        [y r] (cdr/read-f64 r)
        [z r] (cdr/read-f64 r)]
    [{:x x :y y :z z} r]))

(defn encode-point
  "geometry_msgs/Point -> full CDR bytes."
  [p]
  (:bytes (write-point (cdr/encapsulate (cdr/writer)) p)))

(defn decode-point
  "Full CDR bytes -> geometry_msgs/Point EDN map."
  [bytes]
  (first (read-point (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; geometry_msgs/Quaternion -- {:x <float64> :y <float64> :z <float64> :w <float64>}
;; ---------------------------------------------------------------------------

(defn- write-quaternion [w q]
  (-> w
      (cdr/write-f64 (:x q)) (cdr/write-f64 (:y q))
      (cdr/write-f64 (:z q)) (cdr/write-f64 (:w q))))

(defn- read-quaternion [r]
  (let [[x r] (cdr/read-f64 r)
        [y r] (cdr/read-f64 r)
        [z r] (cdr/read-f64 r)
        [w r] (cdr/read-f64 r)]
    [{:x x :y y :z z :w w} r]))

(defn encode-quaternion
  "geometry_msgs/Quaternion -> full CDR bytes."
  [q]
  (:bytes (write-quaternion (cdr/encapsulate (cdr/writer)) q)))

(defn decode-quaternion
  "Full CDR bytes -> geometry_msgs/Quaternion EDN map."
  [bytes]
  (first (read-quaternion (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; geometry_msgs/Pose -- {:position <Point> :orientation <Quaternion>}
;; ---------------------------------------------------------------------------

(defn- write-pose [w p]
  (-> w (write-point (:position p)) (write-quaternion (:orientation p))))

(defn- read-pose [r]
  (let [[position r] (read-point r)
        [orientation r] (read-quaternion r)]
    [{:position position :orientation orientation} r]))

(defn encode-pose
  "geometry_msgs/Pose -> full CDR bytes."
  [p]
  (:bytes (write-pose (cdr/encapsulate (cdr/writer)) p)))

(defn decode-pose
  "Full CDR bytes -> geometry_msgs/Pose EDN map."
  [bytes]
  (first (read-pose (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; geometry_msgs/PoseStamped -- {:header <Header> :pose <Pose>}
;; ---------------------------------------------------------------------------

(defn- write-pose-stamped [w ps]
  (-> w (write-header (:header ps)) (write-pose (:pose ps))))

(defn- read-pose-stamped [r]
  (let [[header r] (read-header r)
        [pose r] (read-pose r)]
    [{:header header :pose pose} r]))

(defn encode-pose-stamped
  "geometry_msgs/PoseStamped -> full CDR bytes."
  [ps]
  (:bytes (write-pose-stamped (cdr/encapsulate (cdr/writer)) ps)))

(defn decode-pose-stamped
  "Full CDR bytes -> geometry_msgs/PoseStamped EDN map."
  [bytes]
  (first (read-pose-stamped (cdr/de-encapsulate (cdr/reader bytes)))))

;; ---------------------------------------------------------------------------
;; sensor_msgs/Joy -- {:header <Header> :axes [<float32>...] :buttons [<int32>...]}
;; A CDR sequence is a uint32 count (aligned to 4) followed by that many
;; elements, each following its own type's alignment.
;; ---------------------------------------------------------------------------

(defn- write-seq [w write-elem xs]
  (reduce write-elem (cdr/write-u32 w (count xs)) xs))

(defn- read-seq [r read-elem]
  (let [[n r] (cdr/read-u32 r)]
    (loop [i 0 r r acc []]
      (if (= i n)
        [acc r]
        (let [[v r] (read-elem r)] (recur (inc i) r (conj acc v)))))))

(defn- write-joy [w j]
  (-> w
      (write-header (:header j))
      (write-seq cdr/write-f32 (:axes j))
      (write-seq cdr/write-i32 (:buttons j))))

(defn- read-joy [r]
  (let [[header r] (read-header r)
        [axes r] (read-seq r cdr/read-f32)
        [buttons r] (read-seq r cdr/read-i32)]
    [{:header header :axes axes :buttons buttons} r]))

(defn encode-joy
  "sensor_msgs/Joy -> full CDR bytes."
  [j]
  (:bytes (write-joy (cdr/encapsulate (cdr/writer)) j)))

(defn decode-joy
  "Full CDR bytes -> sensor_msgs/Joy EDN map."
  [bytes]
  (first (read-joy (cdr/de-encapsulate (cdr/reader bytes)))))
