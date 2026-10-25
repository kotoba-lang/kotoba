(ns browseruse.session)

(defrecord AgentSession [id state hooks])

(defn create-session
  ([] (create-session {}))
  ([{:keys [id hooks] :or {id "default" hooks {}}}]
   (->AgentSession id (atom {:status :running :reason nil}) hooks)))

(defn status [session] (:status @(:state session)))
(defn pause! [session] (swap! (:state session) assoc :status :paused) session)
(defn resume! [session] (swap! (:state session) assoc :status :running :reason nil) session)
(defn stop!
  ([session] (stop! session :requested))
  ([session reason] (swap! (:state session) assoc :status :stopped :reason reason) session))
(defn runnable? [session] (= :running (status session)))
(defn hook! [session hook payload]
  (when-let [f (get (:hooks session) hook)] (f payload)))

