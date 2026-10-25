(ns ctf.adapters.etzhayyim
  (:require [ctf.model :as m]
            [ctf.ports :as p]))

(def yabai-get-risk "ai.gftd.apps.yabai.getRisk")
(def malak-query-risk-chain "ai.gftd.apps.malak.queryRiskChain")

(defprotocol IXrpcClient
  (invoke! [client nsid payload]))

(defn- subject-id [request]
  (let [subject (:ctf/subject request)]
    (or (:subject/id subject)
        (:identity.subject/id subject)
        (:wallet/address subject)
        (:address subject)
        subject)))

(defn- severity->level [severity]
  (case (keyword severity)
    (:critical :deny) :deny
    (:high :challenge) :challenge
    (:medium :review) :review
    (:low :monitor) :monitor
    (:clear :none) :clear
    nil))

(defn- score->level [score]
  (cond
    (nil? score) nil
    (>= score 900) :deny
    (>= score 700) :challenge
    (>= score 400) :review
    (pos? score) :monitor
    :else :clear))

(defn- response-level [response]
  (or (severity->level (:severity response))
      (severity->level (:risk/severity response))
      (score->level (:score response))
      (score->level (:risk/score response))
      :clear))

(defn- response-score [response]
  (or (:score response) (:risk/score response)))

(defn- response-categories [response]
  (set (concat (:categories response)
               (:riskSignals response)
               (:risk/signals response)
               (:threatActors response))))

(defn- evidence-ref [route response]
  (or (:evidence-ref response)
      (:uri response)
      (:cid response)
      (str "xrpc://" (name route) "/" (:request-id response))))

(defn- yabai-payload [request]
  {:entityId (str (subject-id request))
   :caseRef (:ctf/case-ref request)
   :purpose (:ctf/purpose request)})

(defn- malak-payload [request]
  {:address (:ctf/subject request)
   :chain (get-in request [:ctf/request-context :chain])
   :caseRef (:ctf/case-ref request)
   :purpose (:ctf/purpose request)})

(defn- call-route [client route request]
  (case route
    :yabai (invoke! client yabai-get-risk (yabai-payload request))
    :malak (invoke! client malak-query-risk-chain (malak-payload request))))

(defn screening-port [client]
  (reify p/ICtfScreening
    (screen! [_ request route]
      (let [response (call-route client route request)]
        (m/result request route (response-level response)
                  {:score (response-score response)
                   :categories (response-categories response)
                   :evidence-ref (evidence-ref route response)
                   :asserter (str "etzhayyim/" (name route))
                   :observed-at (:observed-at response)})))))
