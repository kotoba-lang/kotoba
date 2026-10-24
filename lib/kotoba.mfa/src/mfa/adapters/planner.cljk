(ns mfa.adapters.planner
  (:require [mfa.model :as m]))

(defprotocol IMfaPlanner
  (plan! [planner payload opts]))

(defn- payload [policy subject context]
  {:policy-id (:mfa.policy/id policy)
   :required (:mfa.policy/required policy)
   :phishing-resistant? (:mfa.policy/phishing-resistant? policy)
   :purpose (:mfa.policy/purpose policy)
   :preferences (:mfa.policy/preferences policy)
   :fallbacks (:mfa.policy/fallbacks policy)
   :fallback-for (:mfa.policy/fallback-for policy)
   :subject subject
   :context context})

(defn plan [planner policy subject context opts]
  (let [response (plan! planner (payload policy subject context) opts)]
    {:mfa.plan/policy-id (:mfa.policy/id policy)
     :mfa.plan/subject subject
     :mfa.plan/factor-requests (:factor-requests response)
     :mfa.plan/fallbacks (:fallbacks response)
     :mfa.plan/evidence-ref (:evidence-ref response)
     :mfa.plan/non-adjudicating true}))

(defn static-plan [policy subject factor-types]
  {:mfa.plan/policy-id (:mfa.policy/id policy)
   :mfa.plan/subject subject
   :mfa.plan/factor-requests (mapv (fn [t] {:authn.factor-request/type t
                                            :authn.factor-request/subject subject})
                                   factor-types)
   :mfa.plan/fallbacks []
   :mfa.plan/non-adjudicating true})
