(ns kotoba.ros.qos
  "ROS 2 QoS (Quality of Service) profiles -- pure EDN data.

  A ROS 2 publisher/subscriber pair only actually connects (DDS calls this
  'matching') when their QoS policies are compatible; a teleop bridge that
  gets this wrong silently drops every message with no error, which is a
  much worse failure mode than a loud one. This namespace does not perform
  the matching decision itself (that is real DDS/rosbridge_suite behavior,
  out of scope for a pure-data contract library) -- it gives a caller the
  same profile shape ROS 2 uses, plus the two presets a teleop bridge needs,
  so the shapes it sends over `kotoba.ros.rosbridge`'s `advertise-op` /
  `subscribe-op` match what the ROS 2 side expects.

  Profile shape: `{:reliability :reliable|:best-effort
                    :durability  :volatile|:transient-local
                    :history     :keep-last|:keep-all
                    :depth       <int>}`")

(def reliability-values #{:reliable :best-effort})
(def durability-values #{:volatile :transient-local})
(def history-values #{:keep-last :keep-all})

(defn valid-qos?
  "True when `q` is a well-formed QoS profile: recognized `:reliability`,
  `:durability`, `:history`, and a non-negative integer `:depth`."
  [q]
  (and (map? q)
       (contains? reliability-values (:reliability q))
       (contains? durability-values (:durability q))
       (contains? history-values (:history q))
       (integer? (:depth q))
       (>= (:depth q) 0)))

(def sensor-data-qos
  "ROS 2's common `qos_profile_sensor_data`: best-effort, volatile,
  keep-last, depth 5. For high-rate sensor streams (e.g. `sensor_msgs/Joy`)
  where a dropped sample is fine but blocking on a slow subscriber is not."
  {:reliability :best-effort
   :durability  :volatile
   :history     :keep-last
   :depth       5})

(def default-qos
  "ROS 2's default profile: reliable, volatile, keep-last, depth 10. For
  command/state topics (e.g. `geometry_msgs/Twist`) where delivery matters
  more than raw throughput."
  {:reliability :reliable
   :durability  :volatile
   :history     :keep-last
   :depth       10})
