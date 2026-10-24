(ns kotoba.captcha.provider)

(defprotocol Provider
  (provider-id [provider])
  (supports-task? [provider task])
  (solve! [provider task context]
    "Returns {:status :ready :solution map}, {:status :retry},
    {:status :waiting-human}, or {:status :failed :error string}."))

(defrecord SyntheticProvider [responder]
  Provider
  (provider-id [_] :synthetic)
  (supports-task? [_ task] (= "SyntheticChallengeTask" (:task/type task)))
  (solve! [_ task context]
    (let [solution (responder (:task/payload task) context)]
      (if (map? solution)
        {:status :ready :solution solution}
        {:status :failed :error "Synthetic responder must return a solution map"}))))

(defn synthetic-provider
  ([] (synthetic-provider (fn [payload _]
                            (if (contains? payload :expected-answer)
                              {:text (:expected-answer payload)}
                              {:synthetic/passed? true}))))
  ([responder] (->SyntheticProvider responder)))

(defrecord HumanProvider [submissions]
  Provider
  (provider-id [_] :human)
  (supports-task? [_ task] (= "HumanVerificationTask" (:task/type task)))
  (solve! [_ task _]
    (if-let [solution (get @submissions (:task/id task))]
      (do (swap! submissions dissoc (:task/id task))
          {:status :ready :solution solution})
      {:status :waiting-human :retry-after-ms 1000})))

(defn human-provider [] (->HumanProvider (atom {})))
(defn submit-human-solution! [provider task-id solution]
  (when-not (map? solution)
    (throw (ex-info "Human solution must be a map" {:task-id task-id})))
  (swap! (:submissions provider) assoc task-id solution)
  true)

(defprotocol VisionBackend
  (analyze-first-party! [backend request context]))

(defrecord VisionProvider [backend]
  Provider
  (provider-id [_] :first-party-vision)
  (supports-task? [_ task] (= "ImageToTextTask" (:task/type task)))
  (solve! [_ task context]
    (let [{:keys [scope owner-confirmed?]} (:task/authorization task)]
      (if (and (= :first-party scope) (true? owner-confirmed?))
        (let [solution (analyze-first-party! backend (:task/payload task) context)]
          (if (map? solution)
            {:status :ready :solution solution}
            {:status :failed :error "Vision backend must return a solution map"}))
        {:status :failed
         :error "Vision processing requires confirmed ownership of a first-party property"}))))

(defn vision-provider [backend] (->VisionProvider backend))

(defn select-provider [providers task]
  (some #(when (supports-task? % task) %) providers))
