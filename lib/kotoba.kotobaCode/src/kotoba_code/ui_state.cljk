(ns kotoba-code.ui-state)

(def initial-state
  {:status :ready
   :messages []
   :tools []
   :error nil
   :turn 0})

(defn reduce-event [state event]
  (case (:event/type event)
    :turn/submitted
    (-> state
        (assoc :status :working :error nil)
        (update :turn inc)
        (update :messages conj {:role :user :text (:text event)}))

    :tool/started
    (update state :tools conj {:id (:id event)
                               :name (:name event)
                               :status :working})

    :tool/completed
    (update state :tools
            (fn [tools]
              (mapv #(if (= (:id %) (:id event))
                       (assoc % :status :done :summary (:summary event))
                       %)
                    tools)))

    :model/fallback
    (update state :messages conj
            {:role :system
             :text (str "OpenRouter credits unavailable; using "
                        (:model event) " for this request.")})

    :system/message
    (-> state
        (assoc :status :ready :error nil :tools [])
        (update :messages conj {:role :system :text (:text event)}))

    :conversation/cleared
    (assoc state :status :ready :messages [] :tools [] :error nil)

    :assistant/completed
    (-> state
        (assoc :status :ready :error nil :tools [])
        (update :messages conj {:role :assistant :text (:text event)}))

    :turn/failed
    (assoc state :status :error :error (:message event) :tools [])

    :turn/cancelled
    (-> state
        (assoc :status :ready :tools [])
        (update :messages conj {:role :system :text "Turn cancelled."}))

    :session/resumed
    (-> state
        (assoc :status :ready :error nil)
        (update :messages conj {:role :system :text "Session resumed."}))

    state))
