(ns ctf.adapters.evidence-ledger
  (:require [identity.adapters.ledger :as ledger]
            [identity.model :as identity]))

(defn result->evidence [request result]
  (identity/evidence-ref (str (:ctf/id result) ":" (name (:ctf/route result)) ":evidence")
                         :screening
                         {:ref (:ctf/evidence-ref result)
                          :source (:ctf/asserter result)
                          :observed-at (:ctf/observed-at result)
                          :non-adjudicating true}))

(defn result->attestation [request result evidence]
  (identity/attestation (str (:ctf/id result) ":" (name (:ctf/route result)) ":attestation")
                        (:ctf/subject request)
                        (keyword "ctf" (name (:ctf/level result)))
                        {:issuer (:ctf/asserter result)
                         :evidence [(:identity.evidence/id evidence)]
                         :issued-at (:ctf/observed-at result)
                         :non-adjudicating true}))

(defn persist-result!
  ([ledger request result] (persist-result! ledger request result {}))
  ([ledger request result opts]
   (let [evidence (result->evidence request result)
         attestation (result->attestation request result evidence)]
     {:evidence-tx (ledger/persist-evidence! ledger evidence opts)
      :attestation-tx (ledger/persist-attestation! ledger attestation opts)
      :identity/evidence evidence
      :identity/attestation attestation})))

(defn persist-screening!
  ([ledger request screening] (persist-screening! ledger request screening {}))
  ([ledger request screening opts]
   (mapv #(persist-result! ledger request % opts) (:ctf/results screening))))
