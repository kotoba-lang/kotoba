(ns rdap.service
  "RDAP query dispatch (RFC 9082) over an `srs` registry, and the HTTP status
  each answer must carry (RFC 7480).

  No HTTP server here: `handle` takes a method and a path and returns
  `{:status :headers :body}` with the body as plain Clojure data. A Worker, a
  Ring handler or a test all call the same function, and the one that runs in
  production is not a different code path from the one that is tested.

  ## The status code is part of the answer

  RFC 7480 §5.3 and §5.4 are specific, and getting them wrong is not cosmetic:

  - **404 for a name that does not exist**, with an RDAP error body. A 200
    carrying an error object is a response intermediaries cache as success.
  - **The `errorCode` member must equal the HTTP status.** Two places to say
    the same thing means two places to disagree.
  - **`application/rdap+json`**, not `application/json`. Clients content-negotiate
    on it, and RFC 7480 §4.2 requires it.
  - **400, not 404, for a syntactically invalid query.** \"Not a well-formed
    domain name\" and \"no such domain\" are different facts, and a registrar
    automating against the API needs to distinguish a bug in its client from a
    name that is free.

  ## Why `/domain/<name>` and not a search

  RFC 9082 §3.1 defines lookup paths; §4 defines *search* paths
  (`/domains?name=…`) and makes them optional. Search is deliberately not
  implemented here: an unbounded search over a registry's whole namespace is a
  bulk-extraction endpoint, and offering one by accident is how registration
  data leaves a registry in bulk. It is refused with 501 — a documented \"not
  implemented\", not a silent 404 that reads as \"no results\"."
  (:require [kotoba.lang.text :as str]
            [rdap.response :as res]
            [rdap.status :as rstatus]
            [srs.core :as srs]
            [srs.time :as t]))

(def content-type "application/rdap+json")

(defn- reply [status body & [extra-headers]]
  {:status status
   :headers (merge {"Content-Type" content-type
                    ;; RFC 7480 §5.6 — RDAP is a public read API and clients
                    ;; are browsers as often as they are scripts.
                    "Access-Control-Allow-Origin" "*"}
                   extra-headers)
   :body body})

(defn- error-reply [status title description]
  (reply status (res/error status title description)))

(def ^:private ldh-name?
  "RFC 1035 §2.3.1 preferred syntax, which is what `ldhName` means: letters,
  digits, hyphens, dot-separated, no leading or trailing hyphen in a label.
  Checked before lookup so an invalid query is a 400 rather than a 404."
  (partial re-matches #"(?i)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+"))

(defn- split-path [path]
  (->> (str/split (or path "") #"/") (remove str/blank?) vec))

(defn handle
  "Answer one RDAP request.

  `opts` carries `:base` (this server's RDAP base URL, used to build `self`
  links), `:tos-url`, and `:registrar-name`."
  [registry method path now & [opts]]
  (let [host-lookup (:host-lookup opts)
        segs (split-path path)
        [kind ident] segs
        opts (or opts {})]
    (cond
      (not (#{:get :head "GET" "HEAD"} method))
      (error-reply 405 "Method Not Allowed" "RDAP is a read-only interface")

      (= kind "help")
      (reply 200 (res/help opts))

      ;; RFC 9082 §4 search paths. Refused explicitly — see the ns docstring.
      (and kind (str/includes? (or path "") "?"))
      (error-reply 501 "Not Implemented"
                   "Search is not offered by this server; use a lookup path (RFC 9082 §3.1)")

      (nil? kind)
      (error-reply 400 "Bad Request"
                   "Expected a lookup path such as /domain/example.com (RFC 9082 §3.1)")

      (not (#{"domain" "nameserver" "entity"} kind))
      (error-reply 400 "Bad Request"
                   (str "Unknown object class: " kind))

      (str/blank? ident)
      (error-reply 400 "Bad Request" (str "Missing " kind " identifier"))

      (= kind "domain")
      (cond
        (not (ldh-name? ident))
        (error-reply 400 "Bad Request"
                     (str "Not a well-formed domain name: " ident))

        :else
        (if-let [d (srs/info registry ident now)]
          ;; A purged name is gone. RDAP has no way to say "existed until
          ;; recently" and inventing one would be a status no client reads.
          (if (= :purged (:domain/phase d))
            (error-reply 404 "Not Found" (str "No such domain: " ident))
            (reply 200 (res/top-level (res/domain d (assoc opts :top-level? false)) opts)
                   ;; RFC 7480 §5.6: the last-changed event is the natural
                   ;; validator, and giving clients one is what keeps a public
                   ;; read API from being re-fetched in full on every poll.
                   (when-let [u (:domain/updated-at d)]
                     {"Last-Modified" (t/iso8601 u)})))
          (error-reply 404 "Not Found" (str "No such domain: " ident))))

      (= kind "nameserver")
      ;; `srs.host` models these now, so they are served — but only when the
      ;; caller supplies a `:host-lookup`. A deployment that stores nameservers
      ;; as plain strings still has nothing to answer with, and 501 stays the
      ;; honest reply there: 404 would be a lie for names that plainly exist in
      ;; the zone.
      (cond
        (not (ldh-name? ident))
        (error-reply 400 "Bad Request" (str "Not a well-formed host name: " ident))

        (nil? host-lookup)
        (error-reply 501 "Not Implemented"
                     "This deployment does not serve nameserver objects; supply :host-lookup")

        :else
        (if-let [h (host-lookup ident)]
          (reply 200 (res/top-level (res/nameserver-object h opts) opts))
          (error-reply 404 "Not Found" (str "No such nameserver: " ident))))

      (= kind "entity")
      (error-reply 501 "Not Implemented"
                   "This registry does not serve entity objects (see srs scope)"))))

(defn domain-status-lines
  "The `Domain Status:` lines a WHOIS response carries, in the EPP spelling
  registrars parse. Exposed here rather than only inside `rdap.whois` because
  the two surfaces must agree about which statuses a domain has, and they can
  only agree by reading the same projection."
  [d]
  (mapv rstatus/whois-line (sort (:domain/statuses d))))
