(ns faceid.model)

(def purposes #{:unlock :step-up :consent :reveal :sign})
(def forbidden-keys #{:raw-face :raw-face-image :face-template :face-embedding :biometric-template})

(defn request [id opts]
  {:faceid/id id
   :faceid/purpose (get opts :purpose :step-up)
   :faceid/challenge (:challenge opts)
   :faceid/rp-id (:rp-id opts)
   :faceid/subject (:subject opts)
   :faceid/created-at (:created-at opts)})

(defn attestation [request ok? opts]
  {:faceid/id (:faceid/id request)
   :faceid/ok? (boolean ok?)
   :faceid/purpose (:faceid/purpose request)
   :faceid/subject (:faceid/subject request)
   :faceid/device-id (:device-id opts)
   :faceid/credential-id (:credential-id opts)
   :faceid/provider (:provider opts)
   :faceid/evidence-ref (:evidence-ref opts)
   :faceid/attested-at (:attested-at opts)})
