(ns saml.core
  "SAML 2.0 as data — 'hiccup for identity federation'. SAML is XML (an OASIS standard), so
   this wraps `xml.core`'s Hiccup emitter with the `samlp`/`saml` element vocabulary, so an
   AuthnRequest / Response / Assertion is composable data you fork and diff. `.cljc`, built on
   xml.core.

     (authn-request {:id \"_req1\" :issue-instant \"2026-07-05T00:00:00Z\"
                      :destination \"https://idp.example/sso\"
                      :issuer \"https://sp.example\"
                      :assertion-consumer-service-url \"https://sp.example/acs\"})
     ⇒ a `[:samlp:AuthnRequest {...} [:saml:Issuer {} \"https://sp.example\"]]` hiccup form —
       pass it to `render` for the XML string.

   Out of scope, host-owned: XML-DSig signing/verification, XML-Enc decryption, and parsing
   *inbound* SAML XML (this library only emits; `parse-attributes` documents the EDN shape a
   host hands back after it has parsed and verified a real assertion)."
  (:require [xml.core :as xml]))

(def ^:const samlp-xmlns "urn:oasis:names:tc:SAML:2.0:protocol")
(def ^:const saml-xmlns "urn:oasis:names:tc:SAML:2.0:assertion")
(def ^:const status-success "urn:oasis:names:tc:SAML:2.0:status:Success")

(defn- attr-name [k]
  (if (keyword? k) (name k) (str k)))

(defn authn-request
  "Build a `<samlp:AuthnRequest>` hiccup form. `protocol-binding` defaults to HTTP-POST."
  [{:keys [id issue-instant destination issuer assertion-consumer-service-url protocol-binding]
    :or {protocol-binding "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"}}]
  [:samlp:AuthnRequest
   {:xmlns:samlp samlp-xmlns
    :xmlns:saml saml-xmlns
    :ID id
    :Version "2.0"
    :IssueInstant issue-instant
    :Destination destination
    :AssertionConsumerServiceURL assertion-consumer-service-url
    :ProtocolBinding protocol-binding}
   [:saml:Issuer {} issuer]])

(defn assertion
  "Build a `<saml:Assertion>` hiccup form. `attributes` is `{attr-name [values...]}` — one
   `<saml:Attribute Name=\"...\">` per key, one `<saml:AttributeValue>` per value."
  [{:keys [id issue-instant issuer subject-name-id conditions-not-before
           conditions-not-on-or-after audience attributes]}]
  [:saml:Assertion
   {:xmlns:saml saml-xmlns :ID id :IssueInstant issue-instant :Version "2.0"}
   [:saml:Issuer {} issuer]
   [:saml:Subject {}
    [:saml:NameID {} subject-name-id]]
   [:saml:Conditions {:NotBefore conditions-not-before :NotOnOrAfter conditions-not-on-or-after}
    [:saml:AudienceRestriction {}
     [:saml:Audience {} audience]]]
   (into [:saml:AttributeStatement {}]
         (for [[k values] attributes]
           (into [:saml:Attribute {:Name (attr-name k)}]
                 (for [v values] [:saml:AttributeValue {} v]))))])

(defn response
  "Wrap an `assertion` (or any hiccup form) in a `<samlp:Response>` with a Status/StatusCode.
   `status-code` defaults to the Success URI."
  [{:keys [id issue-instant destination issuer status-code assertion]
    :or {status-code status-success}}]
  [:samlp:Response
   {:xmlns:samlp samlp-xmlns :xmlns:saml saml-xmlns :ID id :Version "2.0"
    :IssueInstant issue-instant :Destination destination}
   [:saml:Issuer {} issuer]
   [:samlp:Status {}
    [:samlp:StatusCode {:Value status-code}]]
   assertion])

(defn render
  "Render a SAML hiccup form to a standalone XML string (with the `<?xml?>` declaration)."
  [hiccup-form]
  (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" (xml/xml hiccup-form)))

(defn parse-attributes
  "Normalize an *already-parsed* assertion's `:attributes` map — keys become strings, values
   become vectors. This does not parse XML; it documents the shape a host hands back after
   parsing + verifying a real inbound `<saml:Assertion>`."
  [{:keys [attributes] :as parsed-assertion}]
  (assoc parsed-assertion
         :attributes
         (into {} (for [[k v] attributes] [(attr-name k) (vec v)]))))
