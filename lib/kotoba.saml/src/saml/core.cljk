(ns saml.core
  (:require [saml.ports :as p]))

(defn verify [port request assertion-ref]
  (let [out (p/verify-assertion! port request assertion-ref)]
    (when-not (:saml.assertion/ok? out)
      (throw (ex-info "SAML assertion verification failed" {:saml/request request :saml/result out})))
    (when (and (:saml.request/issuer request)
               (= (:saml.request/issuer request) (:saml.assertion/issuer out)))
      (throw (ex-info "SAML assertion issuer must not equal SP issuer" {:saml/request request :saml/result out})))
    (when (and (:saml.request/acs-url request)
               (empty? (:saml.assertion/audience out)))
      (throw (ex-info "SAML assertion audience missing" {:saml/request request :saml/result out})))
    (when (and (:saml.request/issuer request)
               (:saml.assertion/audience out)
               (not= (:saml.request/issuer request) (:saml.assertion/audience out)))
      (throw (ex-info "SAML assertion audience does not match SP issuer" {:saml/request request :saml/result out})))
    out))

(defn verify-once [relay-store port request assertion-ref]
  (when (and (:saml.request/relay-state request)
             (not (p/consume-relay-state! relay-store (:saml.request/relay-state request))))
    (throw (ex-info "SAML RelayState has already been consumed"
                    {:saml/request request})))
  (verify port request assertion-ref))
