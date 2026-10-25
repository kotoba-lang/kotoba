(ns touchid.adapters.apple-local-authentication
  (:require [touchid.adapters.local-auth :as local]))

(defprotocol IAppleLocalAuthentication
  (evaluate-touchid! [client payload opts]))

(defn apple-touchid-client [client]
  (reify local/ILocalAuthentication
    (evaluate-policy! [_ payload opts]
      (evaluate-touchid! client
                         (assoc payload
                                :la/policy :device-owner-authentication-with-biometrics
                                :la/biometry-type :touch-id)
                         opts))))

(defn static-apple-client [response]
  (reify IAppleLocalAuthentication
    (evaluate-touchid! [_ _payload _opts]
      (merge {:provider :apple.local-authentication/touchid} response))))
