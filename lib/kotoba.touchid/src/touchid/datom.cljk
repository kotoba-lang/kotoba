(ns touchid.datom)

(defn attestation-datoms [a]
  [{:db/id (:touchid/id a)
    :touchid/ok? (:touchid/ok? a)
    :touchid/purpose (:touchid/purpose a)
    :touchid/subject (:touchid/subject a)
    :touchid/device-id (:touchid/device-id a)
    :touchid/credential-id (:touchid/credential-id a)
    :touchid/provider (:touchid/provider a)
    :touchid/evidence-ref (:touchid/evidence-ref a)
    :touchid/attested-at (:touchid/attested-at a)}])
