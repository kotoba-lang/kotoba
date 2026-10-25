(ns oidc.core
  (:require [oidc.ports :as p]))

(defn verify [port request token-ref]
  (let [out (p/verify-id-token! port request token-ref)]
    (when-not (:oidc.id-token/ok? out)
      (throw (ex-info "OIDC ID token verification failed" {:oidc/request request :oidc/result out})))
    (when (and (:oidc.request/issuer request)
               (not= (:oidc.request/issuer request) (:oidc.id-token/issuer out)))
      (throw (ex-info "OIDC issuer mismatch" {:oidc/request request :oidc/result out})))
    (when (and (:oidc.request/client-id request)
               (not= (:oidc.request/client-id request) (:oidc.id-token/audience out)))
      (throw (ex-info "OIDC audience mismatch" {:oidc/request request :oidc/result out})))
    (when-not (= (:oidc.request/nonce request) (:oidc.id-token/nonce out))
      (throw (ex-info "OIDC nonce mismatch" {:oidc/request request :oidc/result out})))
    out))

(defn verify-once [port nonce-store request token-ref]
  (when-not (p/consume-nonce! nonce-store (:oidc.request/nonce request))
    (throw (ex-info "OIDC nonce replay" {:oidc/nonce (:oidc.request/nonce request)})))
  (verify port request token-ref))
