(ns faceid.adapters.apple-local-authentication
  (:require [faceid.adapters.local-auth :as local]))

(defprotocol IAppleLocalAuthentication
  (evaluate-faceid! [client payload opts]))

(defn apple-faceid-client [client]
  (reify local/ILocalAuthentication
    (evaluate-policy! [_ payload opts]
      (evaluate-faceid! client
                        (assoc payload
                               :la/policy :device-owner-authentication-with-biometrics
                               :la/biometry-type :face-id)
                        opts))))

(defn static-apple-client [response]
  (reify IAppleLocalAuthentication
    (evaluate-faceid! [_ _payload _opts]
      (merge {:provider :apple.local-authentication/faceid} response))))
