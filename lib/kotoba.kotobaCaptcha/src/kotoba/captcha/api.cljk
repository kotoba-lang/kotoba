(ns kotoba.captcha.api
  (:require [kotoba.captcha.domain :as domain]
            [kotoba.captcha.store :as store]))

(defn- value [m k]
  (or (get m k) (get m (name k))))

(defn- capsolver-task [request]
  (let [task (value request :task)]
    {:type (value task :type)
     :payload (dissoc task :type "type" :authorization "authorization")
     :authorization (or (value task :authorization)
                        (value request :authorization))}))

(defn error-response
  ([code description] (error-response code description nil))
  ([code description task-id]
   (cond-> {:errorId 1 :errorCode code :errorDescription description}
     task-id (assoc :taskId task-id))))

(defn create-task!
  "CapSolver-compatible createTask service function. clientKey is accepted by
  the transport but deliberately not retained in the domain or audit state."
  ([task-store request] (create-task! task-store request {}))
  ([task-store request {:keys [clock id-generator]
                        :or {clock domain/now-ms id-generator domain/task-id}}]
   (let [spec (capsolver-task request)]
     (if-let [{:keys [code description]} (domain/validate-create spec)]
       (error-response code description)
       (let [task (domain/new-task spec (clock) (id-generator))]
         (store/put-task! task-store task)
         {:errorId 0 :taskId (:task/id task)})))))

(defn get-task-result [task-store request]
  (let [id (value request :taskId)]
    (if-let [task (store/get-task task-store id)]
      (let [status (:task/status task)]
        (if (contains? #{:queued :processing} status)
          {:errorId 0 :status "processing"}
          (case status
            :ready {:errorId 0 :status "ready" :solution (:task/result task)}
            :failed (error-response "ERROR_TASK_FAILED"
                                    (or (:task/error task) "Task failed") id)
            :cancelled (error-response "ERROR_TASK_CANCELLED" "Task cancelled" id)
            :expired (error-response "ERROR_TASK_EXPIRED" "Task expired" id))))
      (error-response "ERROR_TASKID_INVALID" "Unknown taskId" id))))

(defn transition-task! [task-store task-id status attrs]
  (store/update-task! task-store task-id
                      #(domain/transition % status attrs (domain/now-ms))))
