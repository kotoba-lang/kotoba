(ns rtl.simulator
  "Event-driven RTL simulator with delta-cycle support (four-valued IEEE
  1164 logic). Restored from kami-rtl's `simulator` module (deleted
  PR #82). The event queue uses a Clojure sorted structure (a vector kept
  sorted on insert, mirroring the original's `BinaryHeap<SimEvent>` min-heap
  ordered by time) rather than a literal binary heap — same externally
  observable ordering (events processed in ascending time order).")

(def logic-values #{:zero :one :x :z})

(defn logic-value->str [v]
  (case v :zero "0" :one "1" :x "x" :z "z"))

(defn logic-and [a b]
  (cond
    (or (= a :zero) (= b :zero)) :zero
    (and (= a :one) (= b :one)) :one
    :else :x))

(defn logic-or [a b]
  (cond
    (or (= a :one) (= b :one)) :one
    (and (= a :zero) (= b :zero)) :zero
    :else :x))

(defn logic-not [a]
  (case a :zero :one :one :zero :x))

(defn signal-state
  "A fresh signal-state of `width` bits, all initialised to `:x`."
  [width]
  {:width width :values (vec (repeat width :x))})

(defn signal-state-from-values [values]
  {:width (count values) :values (vec values)})

(defn simulator
  "A fresh event-driven simulator: time 0, no signals/events/history."
  []
  {:time 0 :event-queue [] :signals {} :history {}})

(defn register-signal
  "Register `name` with `width` bits, initialised to X, empty history."
  [sim name width]
  (-> sim
      (assoc-in [:signals name] (signal-state width))
      (assoc-in [:history name] [])))

(defn- insert-sorted-by-time
  "Insert `event` into `queue` (sorted ascending by `:time`) — keeps the
  event-queue vector sorted, mirroring BinaryHeap<SimEvent> min-heap
  ordering (SimEvent's Ord compares only :time)."
  [queue event]
  (let [idx (count (take-while #(<= (:time %) (:time event)) queue))]
    (vec (concat (subvec queue 0 idx) [event] (subvec queue idx)))))

(defn schedule-event
  "Schedule a value change for `signal` at `time`."
  [sim time signal value]
  (update sim :event-queue insert-sorted-by-time {:time time :signal signal :value value}))

(defn set-input
  "Schedule a value change for `signal` at the simulator's current time."
  [sim signal value]
  (schedule-event sim (:time sim) signal value))

(defn run
  "Run the simulator for `duration` time units, processing events in time
  order up to `time + duration` (inclusive). Advances `:time` to the end
  time even if no events fire that far."
  [sim duration]
  (let [end-time (+ (:time sim) duration)]
    (loop [sim sim]
      (if-let [event (first (:event-queue sim))]
        (if (> (:time event) end-time)
          (assoc sim :time end-time)
          (let [sim (update sim :event-queue subvec 1)
                sim (assoc sim :time (:time event))
                sig (:signal event)
                sim (if (contains? (:signals sim) sig)
                      (update-in sim [:signals sig :values]
                                 (fn [values]
                                   (let [w (count values)
                                         new-len (min (count (:value event)) w)]
                                     (vec (concat (subvec (vec (:value event)) 0 new-len)
                                                  (subvec values new-len))))))
                      sim)
                sim (if (contains? (:history sim) sig)
                      (update-in sim [:history sig] conj {:time (:time event) :value (:value event)})
                      sim)]
            (recur sim)))
        (assoc sim :time end-time)))))

(defn get-signal [sim name] (get (:signals sim) name))
(defn get-signal-history [sim name] (get (:history sim) name))
