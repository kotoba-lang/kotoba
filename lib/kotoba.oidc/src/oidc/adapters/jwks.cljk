(ns oidc.adapters.jwks
  (:require [oidc.model :as m]
            [oidc.ports :as p]))

(defprotocol IJwksVerifier
  (verify-jwt! [verifier token-ref opts]))

(defn- audience [claims]
  (let [aud (:aud claims)]
    (if (sequential? aud) (first aud) aud)))

(defn- result [claims]
  (m/id-token-result (not (:error claims))
                     {:issuer (:iss claims)
                      :audience (audience claims)
                      :subject (:sub claims)
                      :nonce (:nonce claims)
                      :evidence-ref (or (:evidence-ref claims)
                                        (:jwt-ref claims))}))

(defn verifier-port [verifier config]
  (reify p/IOidc
    (verify-id-token! [_ request token-ref]
      (result
       (verify-jwt! verifier token-ref
                    {:issuer (:oidc.request/issuer request)
                     :audience (:oidc.request/client-id request)
                     :jwks-uri (:jwks-uri config)
                     :algorithms (:algorithms config)})))
    (userinfo! [_ access-token-ref]
      (verify-jwt! verifier access-token-ref
                   {:userinfo-endpoint (:userinfo-endpoint config)}))))
