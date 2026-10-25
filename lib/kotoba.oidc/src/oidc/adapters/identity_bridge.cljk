(ns oidc.adapters.identity-bridge
  (:require [identity.model :as identity]
            [oidc.model :as oidc]))

(defn subject-id [claims]
  (str "oidc:" (:iss claims) ":" (:sub claims)))

(defn claims->subject
  ([claims] (claims->subject claims {}))
  ([claims opts]
   (identity/subject (or (:subject-id opts) (subject-id claims))
                     (or (:subject-type opts) :person)
                     {:did (:did claims)
                      :labels (or (:labels opts) #{:oidc})
                      :source (:iss claims)})))

(defn claims->evidence
  ([claims] (claims->evidence claims {}))
  ([claims opts]
   (identity/evidence-ref (or (:evidence-id opts)
                              (str (subject-id claims) ":id-token"))
                          :credential
                          {:ref (or (:jwt-ref claims) (:evidence-ref claims))
                           :source (:iss claims)
                           :observed-at (:observed-at opts)
                           :non-adjudicating true})))

(defn result->subject-evidence
  ([result] (result->subject-evidence result {}))
  ([result opts]
   (let [claims {:iss (:oidc.id-token/issuer result)
                 :sub (:oidc.id-token/subject result)
                 :jwt-ref (:oidc.id-token/evidence-ref result)}]
     {:identity/subject (claims->subject claims opts)
      :identity/evidence (claims->evidence claims opts)
      :oidc/result result})))
