(ns kotoba.swarm-choreo.ros
  "The ROS 2/rosbridge wire path `swarm-choreo` uses to drive one
  performer: `mavros/setpoint_position/local`
  (`geometry_msgs/msg/PoseStamped`) — the real, well-known MAVROS topic a
  PX4/ArduPilot vehicle's MAVROS node subscribes to for an
  offboard/guided position setpoint (real ROS 2/MAVROS convention, not
  invented here — the same \"cite the real topic, don't invent one\"
  discipline `kotoba.teleop.ros` already established for `/cmd_vel`).
  MAVROS namespaces every topic per vehicle (`/<performer-ns>/mavros/...`),
  so `setpoint-topic` takes a performer's ROS namespace, not a bare topic
  string.

  Yaw-only orientation: `kotoba-lang/kami-autodrive`'s planar pose
  convention (`autodrive.types/pose2`, radians CCW from +x) carries no
  roll/pitch, so `->pose-stamped` only ever encodes a rotation about Z —
  correct for a multirotor's yaw-controllable heading, not a claim about
  full 6-DOF attitude.

  Pure data in, pure data out — no socket I/O (host-side, per
  `kotoba.ros.rosbridge`), no CDR encoding here (callers hand the
  PoseStamped-shaped map to `kotoba.ros.msgs/encode-pose-stamped`
  themselves, exactly as `kotoba.teleop.ros` leaves `Twist` encoding to its
  caller)."
  (:require [kotoba.ros.rosbridge :as rosbridge]))

(def setpoint-position-topic-suffix
  "The MAVROS offboard/guided position-setpoint topic suffix, relative to a
  vehicle's own MAVROS namespace."
  "mavros/setpoint_position/local")

(defn setpoint-topic
  "The full setpoint-position topic for a performer running its MAVROS
  node under ROS namespace `performer-ns` (e.g. `\"uas1\"` ->
  `\"/uas1/mavros/setpoint_position/local\"`)."
  [performer-ns]
  (str "/" performer-ns "/" setpoint-position-topic-suffix))

(defn yaw->quaternion
  "Yaw-only (about +Z) `geometry_msgs/Quaternion`: `{:x 0.0 :y 0.0 :z (sin
  yaw/2) :w (cos yaw/2)}`."
  [yaw]
  (let [half (/ yaw 2.0)]
    {:x 0.0 :y 0.0
     :z #?(:clj (Math/sin half) :cljs (js/Math.sin half))
     :w #?(:clj (Math/cos half) :cljs (js/Math.cos half))}))

(defn ->pose-stamped
  "One performer's per-tick setpoint -> a `geometry_msgs/msg/PoseStamped`-
  shaped EDN map. `pos` is a `{:x :y :z}` map (metres); `yaw` radians;
  `stamp` a `builtin_interfaces/Time`-shaped map (`{:sec :nanosec}`,
  supplied by the caller — this namespace has no clock); `:frame_id`
  defaults to `\"map\"` (the standard ROS 2 world-fixed frame a
  PoseStamped setpoint is normally expressed in)."
  [pos yaw stamp & {:keys [frame_id] :or {frame_id "map"}}]
  {:header {:stamp stamp :frame_id frame_id}
   :pose {:position pos :orientation (yaw->quaternion yaw)}})

(defn setpoint-advertise-op
  "rosbridge `advertise` op declaring this client will publish
  `performer-ns`'s setpoint-position topic."
  [performer-ns]
  (rosbridge/advertise-op (setpoint-topic performer-ns)
                          rosbridge/type-geometry-msgs-pose-stamped))

(defn setpoint-publish-op
  "rosbridge `publish` op sending `pose-stamped` (e.g. from
  `->pose-stamped`) to `performer-ns`'s setpoint-position topic."
  [performer-ns pose-stamped]
  (rosbridge/publish-op (setpoint-topic performer-ns) pose-stamped))
