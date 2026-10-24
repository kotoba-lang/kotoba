(ns mfa.adapters.live-risk
  (:require [mfa.adapters.planner :as planner]
            [mfa.adapters.risk-planner :as risk]))

(defprotocol IRiskSignalClient
  (risk-signals! [client subject context opts]))

(defn live-risk-policy-engine
  ([client] (live-risk-policy-engine client {}))
  ([client opts]
   (let [delegate (risk/risk-planner opts)]
     (reify planner/IMfaPlanner
       (plan! [_ payload call-opts]
         (let [signals (risk-signals! client (:subject payload) (:context payload) opts)]
           (planner/plan! delegate
                          (update payload :context merge signals)
                          (merge signals call-opts))))))))

(defn static-risk-client [signals]
  (reify IRiskSignalClient
    (risk-signals! [_ _subject _context _opts] signals)))
