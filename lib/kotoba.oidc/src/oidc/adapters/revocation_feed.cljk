(ns oidc.adapters.revocation-feed
  (:require [oidc.ports :as p]))

(defprotocol IKeyRevocationFeed
  (revoked-key? [feed key-ref opts]))

(defn revocation-aware-port
  ([delegate feed] (revocation-aware-port delegate feed {}))
  ([delegate feed opts]
   (reify p/IOidc
     (verify-id-token! [_ request token-ref]
       (let [out (p/verify-id-token! delegate request token-ref)
             key-ref (or (:oidc.id-token/key-ref out)
                         (:key-ref out))]
         (if (and key-ref (revoked-key? feed key-ref opts))
           (assoc out :oidc.id-token/ok? false
                      :oidc.id-token/revoked-key-ref key-ref)
           out)))
     (userinfo! [_ access-token-ref]
       (p/userinfo! delegate access-token-ref)))))

(defn static-revocation-feed [revoked]
  (let [revoked (set revoked)]
    (reify IKeyRevocationFeed
      (revoked-key? [_ key-ref _opts] (contains? revoked key-ref)))))
