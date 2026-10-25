(ns rdap.whois
  "WHOIS (RFC 3912) — the port-43 text protocol RDAP replaced, rendered from
  the same registry state.

  RFC 3912 is two pages and specifies almost nothing: send a line, read text
  until the connection closes. It defines no response format at all. Everything
  registrars actually parse — `Domain Name:`, `Registry Expiry Date:`,
  `Domain Status:` — comes from ICANN's Registrar Agreement and the gTLD
  Registry Agreement, not from the RFC. So a WHOIS implementation is not
  \"implement RFC 3912\"; it is \"emit the label set every client's regex
  expects\", and the RFC only tells you how to get the bytes there.

  This is kept in the RDAP repository rather than its own because the two are
  one decision with two renderings. A registry that computes statuses twice —
  once for RDAP, once for WHOIS — eventually shows a domain as locked in one
  and unlocked in the other, and the registrant sees whichever they happened to
  query. Both render from `srs.core/info`.

  Two deliberate differences from RDAP:

  - **Statuses keep their EPP camelCase spelling** with the ICANN EPP URL
    appended, because that is what registrar parsers match. RDAP gets the RFC
    8056 space-separated form. This is the one place the two outputs disagree,
    and it is disagreement required by their respective audiences.
  - **Dates are ISO 8601 in UTC.** ICANN requires it, and the historical
    registry-specific formats (`03-Apr-2000`) are the reason WHOIS parsing was
    ever hard.

  New integrations should use RDAP. This exists because port 43 clients still
  exist and a registry that answers RDAP but not WHOIS looks down to them."
  (:require [kotoba.lang.text :as str]
            [rdap.status :as status]
            [srs.time :as t]))

(def ^:private disclaimer
  ["For more information on Whois status codes, please visit https://icann.org/epp"
   ""
   "NOTICE: The expiration date displayed in this record is the date the"
   "registrar's sponsorship of the domain name registration in the registry is"
   "currently set to expire."])

(defn- line [label value]
  (when (and value (not (str/blank? (str value))))
    (str label ": " value)))

(defn domain
  "Render one domain as a WHOIS response body.

  `d` is `srs.core/info`'s projection — the same input RDAP takes, and for the
  same reason: it is already status-projected and already stripped of the
  transfer secret, so this function cannot publish an `authInfo` even if a
  caller hands it the wrong map."
  [d {:keys [registrar-name registrar-url abuse-email abuse-phone
             whois-server now]}]
  (let [nm (:domain/name d)]
    (->> (concat
          [(line "Domain Name" (str/upper nm))
           (line "Registry Domain ID" (str nm "-SRS"))
           (line "Registrar WHOIS Server" whois-server)
           (line "Registrar URL" registrar-url)
           (line "Updated Date" (some-> (:domain/updated-at d) t/iso8601))
           (line "Creation Date" (some-> (:domain/created-at d) t/iso8601))
           (line "Registry Expiry Date" (some-> (:domain/expires-at d) t/iso8601))
           (line "Registrar" (or registrar-name (:domain/registrar d)))
           (line "Registrar IANA ID" (:domain/registrar d))
           (line "Registrar Abuse Contact Email" abuse-email)
           (line "Registrar Abuse Contact Phone" abuse-phone)]
          ;; One line per status, in the EPP spelling with the ICANN URL —
          ;; the format every registrar parser matches on.
          (map #(line "Domain Status" %)
               (map status/whois-line (sort (:domain/statuses d))))
          ;; Registrant contact data is deliberately absent rather than blank.
          ;; A "Registrant Name: REDACTED FOR PRIVACY" line is the ICANN
          ;; convention and says the data exists and is withheld; an empty
          ;; value would say the registrant has no name.
          [(line "Registry Registrant ID" "REDACTED FOR PRIVACY")
           (line "Registrant Name" "REDACTED FOR PRIVACY")
           (line "Registrant Organization" "REDACTED FOR PRIVACY")]
          (map #(line "Name Server" (str/upper %))
               (sort (:domain/nameservers d)))
          [(line "DNSSEC" "unsigned")
           (when now (line ">>> Last update of WHOIS database" (str (t/iso8601 now) " <<<")))
           ""]
          disclaimer)
         (remove nil?)
         (str/join "\r\n"))))

(defn not-found
  "The response for a name with no registration. There is no status code on
  port 43 — the text *is* the answer — so the wording matters: registrar
  clients match on `No match for`, and a registry that phrases it differently
  reads as an error rather than as an available name."
  [name]
  (str/join "\r\n"
            (concat [(str "No match for \"" (str/upper name) "\".")
                     ""]
                    disclaimer)))

(defn respond
  "Answer one port-43 query line. `lookup` is `(fn [name] -> domain-info or
  nil)` so this namespace holds no registry and no clock.

  The query line is trimmed and lower-cased and nothing else: WHOIS clients
  send keyword flags (`domain example.com`, `-T dn example.com`) that mean
  different things at different registries, and quietly interpreting one is how
  a query for a domain returns something else."
  [query-line lookup opts]
  (let [q (some-> query-line str/trim str/lower
                  (str/replace #"\r|\n" ""))]
    (cond
      (str/blank? q) (not-found "")
      (str/includes? q " ")
      (str/join "\r\n" ["Query flags are not supported; send a bare domain name." ""])
      :else (if-let [d (lookup q)] (domain d opts) (not-found q)))))
