(ns faceid.adapters.local-auth
  (:require [faceid.model :as m]
            [faceid.ports :as p]))

(defprotocol ILocalAuthentication
  (evaluate-policy! [client payload opts]))

(defn- payload [request]
  {:id (:faceid/id request)
   :purpose (:faceid/purpose request)
   :challenge (:faceid/challenge request)
   :rp-id (:faceid/rp-id request)
   :subject (:faceid/subject request)
   :created-at (:faceid/created-at request)})

(defn port [client opts]
  (reify p/IFaceID
    (attest! [_ request]
      (let [response (evaluate-policy! client (payload request) opts)]
        (m/attestation request (not (:error response))
                       {:device-id (:device-id response)
                        :credential-id (:credential-id response)
                        :provider (or (:provider response) :local-authentication/faceid)
                        :evidence-ref (:evidence-ref response)
                        :attested-at (:attested-at response)})))))
