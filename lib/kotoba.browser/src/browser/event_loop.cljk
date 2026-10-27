(ns browser.event-loop
  "Deterministic event loop model for compat runtimes.")

(defn empty-loop
  []
  {:loop/now-ms 0
   :loop/next-task-id 1
   :loop/microtasks []
   :loop/timers []
   :loop/ready []})

(defn queue-microtask
  [loop callback-id payload]
  (update loop :loop/microtasks conj {:task/kind :microtask
                                      :callback/id callback-id
                                      :payload payload}))

(defn set-timeout
  [loop callback-id delay-ms payload]
  (let [id (:loop/next-task-id loop)
        due (+ (:loop/now-ms loop) (max 0 (or delay-ms 0)))]
    (-> loop
        (update :loop/next-task-id inc)
        (update :loop/timers conj {:task/id id
                                   :task/kind :timer
                                   :callback/id callback-id
                                   :due-ms due
                                   :payload payload}))))

(defn clear-timeout
  [loop callback-id]
  (let [remove-callback? #(= callback-id (:callback/id %))]
    (-> loop
        (update :loop/timers #(vec (remove remove-callback? %)))
        (update :loop/ready #(vec (remove remove-callback? %))))))

(defn advance
  [loop now-ms]
  (let [{ready true pending false}
        (group-by #(<= (:due-ms %) now-ms) (:loop/timers loop))]
    (-> loop
        (assoc :loop/now-ms now-ms
               :loop/timers (vec pending))
        (update :loop/ready into (sort-by :due-ms ready)))))

(defn drain-once
  [loop]
  (cond
    (seq (:loop/microtasks loop))
    [(first (:loop/microtasks loop))
     (update loop :loop/microtasks #(vec (rest %)))]

    (seq (:loop/ready loop))
    [(first (:loop/ready loop))
     (update loop :loop/ready #(vec (rest %)))]

    :else
    [nil loop]))

(defn drain
  [state]
  (loop [state state
         tasks []]
    (let [[task state] (drain-once state)]
      (if task
        (recur state (conj tasks task))
        {:loop state :tasks tasks}))))
