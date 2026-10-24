(ns saml.datom)

(defn authn-request-datoms [request]
  [{:db/id (:saml.request/id request)
    :saml.request/issuer (:saml.request/issuer request)
    :saml.request/acs-url (:saml.request/acs-url request)
    :saml.request/nameid-format (:saml.request/nameid-format request)
    :saml.request/relay-state (:saml.request/relay-state request)
    :saml.request/created-at (:saml.request/created-at request)}])

(defn assertion-result-datoms [result]
  [{:db/id (str "saml:assertion:" (:saml.assertion/issuer result) ":"
                (:saml.assertion/subject result))
    :saml.assertion/ok? (:saml.assertion/ok? result)
    :saml.assertion/issuer (:saml.assertion/issuer result)
    :saml.assertion/subject (:saml.assertion/subject result)
    :saml.assertion/audience (:saml.assertion/audience result)
    :saml.assertion/not-before (:saml.assertion/not-before result)
    :saml.assertion/not-on-or-after (:saml.assertion/not-on-or-after result)
    :saml.assertion/evidence-ref (:saml.assertion/evidence-ref result)}])
