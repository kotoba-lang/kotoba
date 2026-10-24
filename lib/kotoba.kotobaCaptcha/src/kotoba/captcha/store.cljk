(ns kotoba.captcha.store)

(defprotocol TaskStore
  (put-task! [store task])
  (get-task [store task-id])
  (update-task! [store task-id f])
  (list-tasks [store]))

(defrecord MemoryTaskStore [state]
  TaskStore
  (put-task! [_ task]
    (swap! state assoc (:task/id task) task)
    task)
  (get-task [_ task-id] (get @state task-id))
  (update-task! [_ task-id f]
    (let [missing ::missing
          result (atom missing)]
      (swap! state
             (fn [tasks]
               (if-let [task (get tasks task-id)]
                 (let [updated (f task)]
                   (reset! result updated)
                   (assoc tasks task-id updated))
                 tasks)))
      (when-not (= missing @result) @result)))
  (list-tasks [_] (vals @state)))

(defn memory-store [] (->MemoryTaskStore (atom {})))
