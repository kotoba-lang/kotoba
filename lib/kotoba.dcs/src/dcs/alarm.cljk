(ns dcs.alarm
  "An ISA-18.2-inspired alarm state machine:

    :normal -> :unacked -> :acked -> :normal
                       \\-> :rtn-unacked -> :normal

  Pure — `condition?` and `transition` take the previous state explicitly
  and return the next one; the operator's `ack` action is a separate,
  explicit transition, not driven by the process value.")

(def states
  #{:normal :unacked :acked :rtn-unacked})

(defn- abs* [v] (if (neg? v) (- v) v))

(defn condition?
  "Whether `value` is on the alarm side of `alarm-cfg`'s threshold.
  `active?` is whether the alarm is currently active (any state other than
  :normal): while active, `:hi`/`:hi-hi` require the value to fall back
  below `setpoint - deadband` to clear, and `:lo`/`:lo-lo` require it to
  rise back above `setpoint + deadband` — hysteresis against chatter at the
  boundary. `:dev` (deviation) has no hysteresis: `deadband` is the maximum
  allowed |value - setpoint|."
  [alarm-cfg value active?]
  (let [{:dcs/keys [type setpoint deadband]} alarm-cfg
        deadband (or deadband 0.0)]
    (case type
      (:hi :hi-hi) (if active? (> value (- setpoint deadband)) (> value setpoint))
      (:lo :lo-lo) (if active? (< value (+ setpoint deadband)) (< value setpoint))
      :dev         (> (abs* (- value setpoint)) deadband))))

(defn transition
  "The next alarm state given the previous `state` and whether the trip
  condition is currently true. Returns {:dcs/state' new-state :dcs/event
  (nil, or {:dcs/from prev :dcs/to new-state})}."
  [state condition-true?]
  (let [state' (case state
                 :normal      (if condition-true? :unacked :normal)
                 :unacked     (if condition-true? :unacked :rtn-unacked)
                 :acked       (if condition-true? :acked :normal)
                 :rtn-unacked (if condition-true? :unacked :rtn-unacked))]
    {:dcs/state' state'
     :dcs/event (when (not= state state') {:dcs/from state :dcs/to state'})}))

(defn ack
  "Operator acknowledgment: :unacked -> :acked; :rtn-unacked -> :normal;
  otherwise a no-op (nothing to acknowledge in this state)."
  [state]
  (case state
    :unacked     :acked
    :rtn-unacked :normal
    state))

(defn step
  "Combine `condition?` + `transition` for one scan-cycle evaluation of
  `alarm-cfg` against `value`, given the previous `state` (`:normal` if this
  is the first scan). Returns {:dcs/state' state' :dcs/event event-or-nil}."
  ([alarm-cfg value] (step alarm-cfg value :normal))
  ([alarm-cfg value state]
   (transition state (condition? alarm-cfg value (not= state :normal)))))
