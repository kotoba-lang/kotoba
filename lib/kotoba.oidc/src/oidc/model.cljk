(ns oidc.model)

(defn auth-request [id opts]
  {:oidc.request/id id
   :oidc.request/issuer (:issuer opts)
   :oidc.request/client-id (:client-id opts)
   :oidc.request/redirect-uri (:redirect-uri opts)
   :oidc.request/scope (set (or (:scope opts) #{"openid"}))
   :oidc.request/state (:state opts)
   :oidc.request/nonce (:nonce opts)})

(defn id-token-result [ok? opts]
  {:oidc.id-token/ok? (boolean ok?)
   :oidc.id-token/issuer (:issuer opts)
   :oidc.id-token/audience (:audience opts)
   :oidc.id-token/subject (:subject opts)
   :oidc.id-token/nonce (:nonce opts)
   :oidc.id-token/evidence-ref (:evidence-ref opts)})
