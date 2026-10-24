(ns saml.model)

(defn authn-request [id opts]
  {:saml.request/id id
   :saml.request/issuer (:issuer opts)
   :saml.request/acs-url (:acs-url opts)
   :saml.request/nameid-format (:nameid-format opts)
   :saml.request/relay-state (:relay-state opts)
   :saml.request/created-at (:created-at opts)})

(defn assertion-result [ok? opts]
  {:saml.assertion/ok? (boolean ok?)
   :saml.assertion/issuer (:issuer opts)
   :saml.assertion/subject (:subject opts)
   :saml.assertion/audience (:audience opts)
   :saml.assertion/not-before (:not-before opts)
   :saml.assertion/not-on-or-after (:not-on-or-after opts)
   :saml.assertion/evidence-ref (:evidence-ref opts)})
