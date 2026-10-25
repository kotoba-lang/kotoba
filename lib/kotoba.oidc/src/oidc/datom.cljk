(ns oidc.datom)

(defn auth-request-datoms [request]
  [{:db/id (:oidc.request/id request)
    :oidc.request/issuer (:oidc.request/issuer request)
    :oidc.request/client-id (:oidc.request/client-id request)
    :oidc.request/redirect-uri (:oidc.request/redirect-uri request)
    :oidc.request/scope (:oidc.request/scope request)
    :oidc.request/state (:oidc.request/state request)
    :oidc.request/nonce (:oidc.request/nonce request)}])

(defn id-token-result-datoms [result]
  [{:db/id (str "oidc:id-token:" (:oidc.id-token/issuer result) ":"
                (:oidc.id-token/subject result))
    :oidc.id-token/ok? (:oidc.id-token/ok? result)
    :oidc.id-token/issuer (:oidc.id-token/issuer result)
    :oidc.id-token/audience (:oidc.id-token/audience result)
    :oidc.id-token/subject (:oidc.id-token/subject result)
    :oidc.id-token/nonce (:oidc.id-token/nonce result)
    :oidc.id-token/evidence-ref (:oidc.id-token/evidence-ref result)}])
