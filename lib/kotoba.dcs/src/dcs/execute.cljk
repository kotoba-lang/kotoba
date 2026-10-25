(ns dcs.execute
  "The scan-cycle engine: one pass over a dcs.model system, advancing every
  :auto control loop's PID and every alarm's state machine. Pure over the
  `io` argument (a dcs.ports/IFieldIO implementation the host supplies) —
  the engine itself performs no I/O."
  (:require [dcs.model :as m]
            [dcs.pid :as pid]
            [dcs.alarm :as alarm]
            [dcs.ports :as ports]))

(defn- scan-loop [lp pid-states io dt]
  (if (not= :auto (:dcs/mode lp))
    pid-states
    (let [pv        (ports/read-tag io (:dcs/pv-tag lp))
          state     (get pid-states (:dcs/id lp) (pid/init-state))
          {:dcs/keys [output state']}
          (pid/step (:dcs/tuning lp) state pv (:dcs/setpoint lp) dt (:dcs/output-limits lp))]
      (ports/write-tag! io (:dcs/output-tag lp) output)
      (assoc pid-states (:dcs/id lp) state'))))

(defn- scan-alarm [al alarm-states io]
  (let [value (ports/read-tag io (:dcs/tag al))
        prior (get alarm-states (:dcs/id al) :normal)
        {:dcs/keys [state' event]} (alarm/step al value prior)]
    [(assoc alarm-states (:dcs/id al) state')
     (when event (assoc event :dcs/alarm (:dcs/id al)))]))

(defn init-state
  "A fresh scan-loop state, threaded across successive `scan` calls."
  []
  {:dcs/pid {} :dcs/alarm {}})

(defn scan
  "Run one scan cycle of `system` against `io`, threading `state` (as
  returned by this fn; `(init-state)` for the first scan). `dt` is the
  elapsed seconds since the previous scan. Returns {:dcs/state' state'
  :dcs/events [...]} — events are alarm transitions this cycle
  (chronological, one entry per alarm that changed state this scan).
  :manual and :cascade loops are skipped (their output/setpoint is driven
  externally — by an operator or a master loop, respectively)."
  [system state io dt]
  (let [pid-state'   (reduce (fn [s lp] (scan-loop lp s io dt))
                              (:dcs/pid state)
                              (m/loops system))
        [alarm-state' events]
        (reduce (fn [[s evs] al]
                  (let [[s' ev] (scan-alarm al s io)]
                    [s' (cond-> evs ev (conj ev))]))
                [(:dcs/alarm state) []]
                (m/alarms system))]
    {:dcs/state' {:dcs/pid pid-state' :dcs/alarm alarm-state'}
     :dcs/events events}))
