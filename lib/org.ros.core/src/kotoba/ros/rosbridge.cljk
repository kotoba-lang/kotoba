(ns kotoba.ros.rosbridge
  "rosbridge v2 protocol -- pure EDN-map constructors/parsers for the ops a
  teleop bridge needs.

  rosbridge (`rosbridge_suite`, which supports ROS 2) is the standard,
  widely-documented way non-native ROS clients (roslibjs, roslibpy, and many
  others) talk to a *live* ROS 2 node without implementing DDS themselves:
  a JSON-shaped protocol carried over any transport, typically WebSocket.

  This namespace works purely at the EDN-map level. It does NOT parse or
  serialize JSON strings and does NOT open a socket -- both are deliberately
  left to a host-side caller (e.g. a `.clj`/`.cljs` process that owns a
  WebSocket and a JSON codec). That keeps this namespace, like the rest of
  `org-ros`, pure data in / pure data out: no network, no I/O.

  Message type-strings use the ROS 2 (not ROS 1) convention, which inserts a
  `/msg/` middle segment: `\"geometry_msgs/msg/Twist\"`, not
  `\"geometry_msgs/Twist\"`. The constants below are the ROS 2 type-strings
  for exactly the message shapes `kotoba.ros.msgs` implements, so callers
  never have to hand-type or typo them.")

;; ---------------------------------------------------------------------------
;; ROS 2 message type-strings for kotoba.ros.msgs's message shapes
;; ---------------------------------------------------------------------------

(def type-std-msgs-header "std_msgs/msg/Header")
(def type-std-msgs-bool "std_msgs/msg/Bool")
(def type-geometry-msgs-twist "geometry_msgs/msg/Twist")
(def type-geometry-msgs-twist-stamped "geometry_msgs/msg/TwistStamped")
(def type-geometry-msgs-point "geometry_msgs/msg/Point")
(def type-geometry-msgs-quaternion "geometry_msgs/msg/Quaternion")
(def type-geometry-msgs-pose "geometry_msgs/msg/Pose")
(def type-geometry-msgs-pose-stamped "geometry_msgs/msg/PoseStamped")
(def type-sensor-msgs-joy "sensor_msgs/msg/Joy")

;; ---------------------------------------------------------------------------
;; Op constructors
;; ---------------------------------------------------------------------------

(defn advertise-op
  "`{:op \"advertise\" ...}` -- declare that this client will publish `topic`
  as ROS 2 message `type` (one of the `type-*` constants above, or any ROS 2
  type-string)."
  [topic type]
  {:op "advertise" :topic topic :type type})

(defn unadvertise-op
  "`{:op \"unadvertise\" ...}` -- stop publishing `topic`."
  [topic]
  {:op "unadvertise" :topic topic})

(defn publish-op
  "`{:op \"publish\" ...}` -- publish EDN map `msg` (the JSON-shaped rosbridge
  message body, e.g. matching a `kotoba.ros.msgs` shape) to `topic`."
  [topic msg]
  {:op "publish" :topic topic :msg msg})

(defn subscribe-op
  "`{:op \"subscribe\" ...}` -- subscribe to `topic`, expecting ROS 2 message
  `type`."
  [topic type]
  {:op "subscribe" :topic topic :type type})

(defn unsubscribe-op
  "`{:op \"unsubscribe\" ...}` -- stop receiving `topic`."
  [topic]
  {:op "unsubscribe" :topic topic})

;; ---------------------------------------------------------------------------
;; Op parser
;; ---------------------------------------------------------------------------

(def recognized-ops
  "The rosbridge v2 op names this namespace understands -- exactly the ones a
  teleop bridge needs to send/receive. rosbridge defines more ops
  (`call_service`, `status`, `png`, …); anything outside this set is
  deliberately treated as unrecognized by `parse-op` rather than silently
  passed through."
  #{"advertise" "unadvertise" "publish" "subscribe" "unsubscribe"})

(defn parse-op
  "Validate that EDN map `m` has a recognized `:op`. Returns `m` unchanged
  (already the normalized/tagged shape callers need -- `:op` plus whatever
  op-specific keys are present) when `:op` is recognized, or `nil`
  otherwise. `m` is expected to already be parsed from JSON into an EDN map
  by the host-side caller; this function does no JSON work itself."
  [m]
  (when (and (map? m) (contains? recognized-ops (:op m)))
    m))
