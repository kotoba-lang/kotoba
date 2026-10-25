(ns touchid.adapters.local-auth
  (:require [touchid.model :as m]
            [touchid.ports :as p]))

(defprotocol ILocalAuthentication
  (evaluate-policy! [client payload opts]))

(defn- payload [request]
  {:id (:touchid/id request)
   :purpose (:touchid/purpose request)
   :challenge (:touchid/challenge request)
   :rp-id (:touchid/rp-id request)
   :subject (:touchid/subject request)
   :created-at (:touchid/created-at request)})

(defn port [client opts]
  (reify p/ITouchID
    (attest! [_ request]
      (let [response (evaluate-policy! client (payload request) opts)]
        (m/attestation request (not (:error response))
                       {:device-id (:device-id response)
                        :credential-id (:credential-id response)
                        :provider (or (:provider response) :local-authentication/touchid)
                        :evidence-ref (:evidence-ref response)
                        :attested-at (:attested-at response)})))))
