(ns faceid.datom)

(defn attestation-datoms [a]
  [{:db/id (:faceid/id a)
    :faceid/ok? (:faceid/ok? a)
    :faceid/purpose (:faceid/purpose a)
    :faceid/subject (:faceid/subject a)
    :faceid/device-id (:faceid/device-id a)
    :faceid/credential-id (:faceid/credential-id a)
    :faceid/provider (:faceid/provider a)
    :faceid/evidence-ref (:faceid/evidence-ref a)
    :faceid/attested-at (:faceid/attested-at a)}])
