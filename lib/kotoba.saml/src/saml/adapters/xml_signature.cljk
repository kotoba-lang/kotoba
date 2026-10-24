(ns saml.adapters.xml-signature
  (:require [saml.adapters.xml :as xml]
            [saml.ports :as p]))

(defprotocol ITrustChainPolicy
  (trusted? [policy claims opts]))

(defn signature-verifier-port
  ([signature-verifier trust-policy] (signature-verifier-port signature-verifier trust-policy {}))
  ([signature-verifier trust-policy opts]
   (let [delegate (xml/verifier-port signature-verifier opts)]
     (reify p/ISaml
       (verify-assertion! [_ request assertion-ref]
         (let [out (p/verify-assertion! delegate request assertion-ref)]
           (if (trusted? trust-policy out opts)
             out
             (assoc out :saml.assertion/ok? false
                        :saml.assertion/trust-chain? false))))))))

(defn static-trust-policy [ok?]
  (reify ITrustChainPolicy
    (trusted? [_ _claims _opts] (boolean ok?))))
