(ns saml.adapters.xml
  (:require [saml.model :as m]
            [saml.ports :as p]))

(defprotocol IXmlSignatureVerifier
  (verify-saml! [verifier assertion-ref opts]))

(defn- assertion-result [claims]
  (m/assertion-result (not (:error claims))
                      {:issuer (:issuer claims)
                       :subject (:subject claims)
                       :audience (:audience claims)
                       :not-before (:not-before claims)
                       :not-on-or-after (:not-on-or-after claims)
                       :evidence-ref (or (:evidence-ref claims)
                                         (:assertion-ref claims))}))

(defn verifier-port [verifier config]
  (reify p/ISaml
    (verify-assertion! [_ request assertion-ref]
      (assertion-result
       (verify-saml! verifier assertion-ref
                     {:sp-issuer (:saml.request/issuer request)
                      :acs-url (:saml.request/acs-url request)
                      :idp-metadata-ref (:idp-metadata-ref config)
                      :trusted-cert-refs (:trusted-cert-refs config)})))))
