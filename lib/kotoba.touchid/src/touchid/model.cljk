(ns touchid.model)

(def purposes #{:unlock :step-up :consent :reveal :sign})
(def forbidden-keys #{:raw-fingerprint :fingerprint-template :touch-template :biometric-template})

(defn request [id opts]
  {:touchid/id id
   :touchid/purpose (get opts :purpose :step-up)
   :touchid/challenge (:challenge opts)
   :touchid/rp-id (:rp-id opts)
   :touchid/subject (:subject opts)
   :touchid/created-at (:created-at opts)})

(defn attestation [request ok? opts]
  {:touchid/id (:touchid/id request)
   :touchid/ok? (boolean ok?)
   :touchid/purpose (:touchid/purpose request)
   :touchid/subject (:touchid/subject request)
   :touchid/device-id (:device-id opts)
   :touchid/credential-id (:credential-id opts)
   :touchid/provider (:provider opts)
   :touchid/evidence-ref (:evidence-ref opts)
   :touchid/attested-at (:attested-at opts)})
