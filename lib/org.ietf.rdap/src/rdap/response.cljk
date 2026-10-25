(ns rdap.response
  "RDAP response objects (RFC 9083) built from `srs` registry state.

  RDAP replaced WHOIS to make registration data *parseable*: WHOIS is
  free-form text that every registry formats differently, and clients parse it
  with regexes that break whenever a registry changes a label. So the value of
  RDAP is entirely in getting the structure right — a JSON body with invented
  member names is a WHOIS response with extra punctuation.

  Three structures carry almost all of it, and each has a rule that is easy to
  miss:

  **`rdapConformance`** must be present on every *top-level* response and
  absent from nested objects (RFC 9083 §4.1). It is how a client knows which
  extensions the server speaks. Repeating it inside an embedded entity is a
  common bug that makes responses larger and no more informative.

  **`events`** is where dates live — there is no `registered` or `expires`
  member. Each event is an `eventAction` from the IANA registry plus an
  `eventDate`. Inventing `\"eventAction\": \"expires\"` instead of the
  registered `\"expiration\"` produces a body no client will read.

  **`entities`** carry contact data as jCard (RFC 7095), which is vCard in
  JSON: an array `[\"vcard\", [[property, params, type, value], …]]`. It is a
  strange shape to hand-build and stranger to get wrong quietly, so
  `rdap.jcard` builds it rather than each call site.

  Everything here is data — plain Clojure maps and vectors. `kotoba-lang/json`
  serializes them, and nothing in this namespace touches HTTP."
  (:require [kotoba.lang.text] [rdap.jcard :as jcard]
            [rdap.status :as status]
            [srs.time :as t]))

(def conformance
  "RFC 9083 §4.1. `rdap_level_0` is the base; anything else here is an
  extension identifier from the IANA RDAP Extensions registry, and claiming one
  the server does not implement is worse than claiming none."
  ["rdap_level_0"])

(defn- event [action at]
  (when at {"eventAction" action "eventDate" (t/iso8601 at)}))

(defn- link [rel href type]
  {"value" href "rel" rel "href" href "type" (or type "application/rdap+json")})

(defn- self-link [base kind ident]
  (link "self" (str base "/" kind "/" ident) nil))

(defn notices
  "RFC 9083 §4.3. The terms-of-service and status-codes notices are not
  decoration: ICANN's RDAP profile requires a registry to state the terms under
  which the data is provided, and clients display it. A response without them
  is incomplete rather than merely terse."
  [{:keys [tos-url terms]}]
  (cond-> [{"title" "Status Codes"
            "description" ["For more information on domain status codes, please visit https://icann.org/epp"]
            "links" [(link "glossary" "https://icann.org/epp" "text/html")]}]
    tos-url
    (conj {"title" "Terms of Service"
           "description" [(or terms "Service subject to Terms of Service.")]
           "links" [(link "terms-of-service" tos-url "text/html")]})))

;; ── entities ──────────────────────────────────────────────────────────────

(defn entity
  "An `entity` object (RFC 9083 §5.1). `roles` are from the IANA registry —
  `registrant`, `registrar`, `technical`, `administrative`, `abuse`.

  `:redacted?` produces an entity with roles and a handle but no jCard. That is
  the honest shape for a registry that does not publish registrant contact data
  (which, post-GDPR, is most of them): the entity exists, its role is known,
  and the contact detail is withheld. Omitting the entity entirely instead
  would tell a client there is no registrant."
  [{:keys [handle roles name org email phone address redacted? base]}]
  (cond-> {"objectClassName" "entity"
           "roles" (vec roles)}
    handle (assoc "handle" handle)
    (and base handle) (assoc "links" [(self-link base "entity" handle)])
    (not redacted?)
    (assoc "vcardArray" (jcard/vcard {:name name :org org :email email
                                      :phone phone :address address}))))

;; ── nameservers ───────────────────────────────────────────────────────────

(defn nameserver
  "A `nameserver` object (RFC 9083 §5.2). `ipAddresses` is present only for a
  nameserver inside the registry's own zone — glue. For an out-of-zone
  nameserver the registry holds no addresses, and inventing an empty
  `ipAddresses` object asserts that it has none rather than that it does not
  know."
  [{:keys [name v4 v6 base]}]
  (cond-> {"objectClassName" "nameserver"
           "ldhName" name}
    base (assoc "links" [(self-link base "nameserver" name)])
    (or (seq v4) (seq v6))
    (assoc "ipAddresses" (cond-> {}
                           (seq v4) (assoc "v4" (vec v4))
                           (seq v6) (assoc "v6" (vec v6))))))

;; ── domains ───────────────────────────────────────────────────────────────

(defn nameserver-object
  "A top-level `nameserver` object (RFC 9083 §5.2) built from an `srs.host`
  projection.

  `ipAddresses` appears only when the host actually has addresses — which, per
  RFC 5732 §1.1, is exactly the in-zone case. For an out-of-zone host the
  registry is not authoritative and holds none, and emitting an empty
  `ipAddresses` object would assert it has none rather than that the registry
  does not know.

  `linked` reaches RDAP as a status via the same RFC 8056 projection every
  other status goes through, so a client reads it the same way. The *list* of
  linked domains is not published: `srs.host/info` already reports a count, and
  which domains use a nameserver is not something a public lookup should
  enumerate."
  [h {:keys [base]}]
  (let [addrs (:host/addresses h)
        v4 (filterv #(not (kotoba.lang.text/includes? % ":")) addrs)
        v6 (filterv #(kotoba.lang.text/includes? % ":") addrs)]
    (cond-> {"objectClassName" "nameserver"
             "handle" (str (:host/name h) "-SRS")
             "ldhName" (:host/name h)
             "status" (status/project (:host/statuses h))
             "events" (into [] (keep identity)
                            [(event "registration" (:host/created-at h))
                             (event "last changed" (:host/updated-at h))])}
      (seq addrs)
      (assoc "ipAddresses" (cond-> {}
                             (seq v4) (assoc "v4" v4)
                             (seq v6) (assoc "v6" v6)))
      (:host/registrar h)
      (assoc "entities" [(entity {:handle (:host/registrar h) :roles ["registrar"]
                                  :org (:host/registrar h) :base base})])
      base (assoc "links" [(self-link base "nameserver" (:host/name h))]))))

(defn domain
  "A `domain` object (RFC 9083 §5.3) built from an `srs` domain.

  `d` is the projection from `srs.core/info` — already status-projected and
  already stripped of `authInfo`. Taking the projection rather than the raw
  record is deliberate: RDAP is public, and a function that accepted the stored
  record could publish the transfer secret if a caller passed the wrong map."
  [d {:keys [base registrar-name unicode-name top-level?]}]
  (let [nm (:domain/name d)]
    (cond-> {"objectClassName" "domain"
             "handle" (str nm "-SRS")
             "ldhName" nm
             "status" (status/project (:domain/statuses d))
             "events" (into [] (keep identity)
                            [(event "registration" (:domain/created-at d))
                             (event "expiration" (:domain/expires-at d))
                             (event "last changed" (:domain/updated-at d))
                             (event "transfer" (:domain/transferred-at d))])
             "entities" (cond-> []
                          (:domain/registrar d)
                          (conj (entity {:handle (:domain/registrar d)
                                         :roles ["registrar"]
                                         :org (or registrar-name (:domain/registrar d))
                                         :base base}))
                          (:domain/registrant d)
                          (conj (entity {:handle (:domain/registrant d)
                                         :roles ["registrant"]
                                         :redacted? true
                                         :base base})))}
      ;; RFC 9083 §5.3: unicodeName is present only when the name is an IDN.
      ;; Emitting it equal to ldhName for an ASCII name is noise a client has
      ;; to decide to ignore.
      (and unicode-name (not= unicode-name nm)) (assoc "unicodeName" unicode-name)
      (seq (:domain/nameservers d))
      (assoc "nameservers" (mapv #(nameserver {:name % :base base})
                                 (:domain/nameservers d)))
      base (assoc "links" [(self-link base "domain" nm)])
      top-level? (assoc "rdapConformance" conformance))))

(defn top-level
  "Add the members that belong only on a top-level response: the conformance
  array and the server's notices. Kept separate from `domain` so that an
  embedded object cannot accidentally carry them (RFC 9083 §4.1)."
  [obj opts]
  (assoc obj
         "rdapConformance" conformance
         "notices" (notices opts)))

;; ── errors ────────────────────────────────────────────────────────────────

(defn error
  "An RDAP error response (RFC 9083 §6). The HTTP status and the
  `errorCode` member must agree — a body saying 404 delivered with a 200 is a
  response some clients cache as a successful answer."
  [code title description]
  {"rdapConformance" conformance
   "errorCode" code
   "title" title
   "description" (if (string? description) [description] (vec description))})

(defn help
  "The `/help` response (RFC 9082 §3.1.6). Required, and the natural place for
  the terms of service, because it is the one path a client may fetch without
  knowing any object."
  [opts]
  {"rdapConformance" conformance
   "notices" (notices opts)})
