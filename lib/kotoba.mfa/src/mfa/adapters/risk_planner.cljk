(ns mfa.adapters.risk-planner
  (:require [mfa.adapters.planner :as planner]))

(def risk-order {:low 0 :medium 1 :high 2 :critical 3})

(defn- factor-request [subject t]
  {:authn.factor-request/type t
   :authn.factor-request/subject subject})

(defn- preference-rank [preferences]
  (zipmap preferences (range)))

(defn- order-factors [preferences factors]
  (let [rank (preference-rank preferences)
        fallback-rank (count preferences)]
    (sort-by #(get rank % fallback-rank) factors)))

(defn- ensure-phishing-resistant [required]
  (if (some #{:webauthn :passkey :faceid :touchid} required)
    required
    (conj (vec required) :webauthn)))

(defn- plan-factors [payload risk]
  (let [required (vec (:required payload))
        required (if (:phishing-resistant? payload)
                   (ensure-phishing-resistant required)
                   required)]
    (case risk
      (:critical :high) (ensure-phishing-resistant required)
      :medium (if (< (count required) 2)
                (conj required :totp)
                required)
      required)))

(defn risk-planner
  ([] (risk-planner {}))
  ([opts]
   (reify planner/IMfaPlanner
     (plan! [_ payload call-opts]
       (let [risk (or (:risk call-opts)
                      (get-in payload [:context :risk])
                      (:default-risk opts)
                      :low)
             factors (->> (plan-factors payload risk)
                          distinct
                          (order-factors (or (:preferences payload)
                                             (:preferences opts))))]
         {:factor-requests (mapv #(factor-request (:subject payload) %) factors)
          :fallbacks (vec (remove (set factors)
                                  (concat (:fallbacks payload)
                                          (:fallbacks opts))))
          :evidence-ref (:evidence-ref call-opts)})))))
