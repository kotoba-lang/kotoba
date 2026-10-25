;; mst_projector.cljc — mst-projector XRPC client (cljc port of mst_projector.py, ADR
;; clj/bb repo rule). Wraps the 4 query_api endpoints; `httpx.AsyncClient` is replaced by
;; `babashka.http-client` (no new dependency — bb-native). Per ADR-2605215500 §5 M5.
;;
;; Config: ETZHAYYIM_MST_PROJECTOR_URL (REQUIRED — no default).
;;
;; WHY THE ENDPOINT HAS NO DEFAULT:
;;   This module used to fall back to a literal "http://simeon.local:8765". `.local` is the
;;   mDNS/Bonjour namespace (RFC 6762), so that name is claimable by any host on the same
;;   link, and `simeon` is a private murakumo fleet node reachable only on the operator's own
;;   network. Nothing here carries a credential — `default-request` sets content-type and
;;   nothing else, and the transport signature has no header slot at all — so the exposure is
;;   narrower than llm.cljc's: query bodies (collection names, author DIDs) went to whoever
;;   answered, and the reply was parsed and trusted as record data. That is still a host
;;   nobody chose, and no public endpoint serves this projector, so the SDK asks for the
;;   address instead of inventing one.
;;
;; Testability (≈ python `_inject_transport`): all I/O goes through the dynamic var
;; `*request*`. Tests `(binding [*request* stub] …)` to avoid real network calls; the stub
;; takes [url body-string] and returns a ring-ish {:status int :body string} (or throws to
;; simulate a transport-level failure, which `call*` wraps as ::mst-projector-network-error).
;;
;; Endpoints/params/return shapes are faithful to the python: same NSIDs, same wire keys
;; (camelCase fieldName/fieldValue), responses parsed to Clojure maps with keyword keys.
(ns etzhayyim-sdk.mst-projector
  (:require [etzhayyim-sdk.config :as cfg]
            [etzhayyim-sdk.errors :as err]
            #?(:clj [cheshire.core :as json])
            #?(:clj [babashka.http-client :as http])))

(defn resolve-base-url
  "Normalize *raw* (an ETZHAYYIM_MST_PROJECTOR_URL value) into the mst-projector base URL.

  Throws ::err/mst-projector-config-error when *raw* names no host — nil, blank, or nothing
  but slashes. There is deliberately no fallback; see the note at the top of this file. Pure,
  so the refusal is testable without touching the environment.

  This trims and strips trailing slashes, which the previous `or` did not: python parity on
  that point produced \"  /xrpc/…\" from a whitespace value and a doubled \"//\" from a
  trailing slash, neither of which addresses anything."
  [raw]
  (or (cfg/normalize-base-url raw)
      (throw (err/ex ::err/mst-projector-config-error
                     (str "ETZHAYYIM_MST_PROJECTOR_URL is not set. This client POSTs queries "
                          "to the configured host and trusts the records it returns, so it "
                          "must be one you chose — point ETZHAYYIM_MST_PROJECTOR_URL at your "
                          "mst-projector. It has no default.")
                     {:env-var "ETZHAYYIM_MST_PROJECTOR_URL"}))))

(defn base-url
  "mst-projector server base URL from ETZHAYYIM_MST_PROJECTOR_URL. Required — throws
  ::err/mst-projector-config-error when unset rather than guessing a host."
  []
  (resolve-base-url #?(:clj (System/getenv "ETZHAYYIM_MST_PROJECTOR_URL") :cljs nil)))

(defn- default-request
  "Default transport: POST *body-str* as JSON to *url*, return {:status :body} WITHOUT
  throwing on 4xx/5xx (`:throw false`) so `call*` can classify the status. Throws only on a
  genuine transport failure (connection refused / timeout)."
  [url body-str]
  #?(:clj (http/post url {:headers {"content-type" "application/json"}
                          :body body-str
                          :throw false})
     :cljs (throw (ex-info "default-request unavailable on cljs; bind *request*" {:url url}))))

(def ^:dynamic *request*
  "Pluggable POST transport (testability hook, ≈ python _inject_transport). When nil the
  bb-native `default-request` is used."
  nil)

(defn- subs200 [s] (let [s (str s)] (subs s 0 (min 200 (count s)))))

(defn- call*
  "POST to /xrpc/<nsid> with JSON *body*, return the parsed response map. Mirrors the python
  status classification: transport error → ::mst-projector-network-error, 5xx →
  ::mst-projector-server-error, 4xx → ::mst-projector-error, else parsed JSON."
  [nsid body]
  (let [url (str (base-url) "/xrpc/" nsid)
        body-str #?(:clj (json/generate-string body) :cljs (throw (ex-info "cljs json" {})))
        resp (try ((or *request* default-request) url body-str)
                  (catch #?(:clj Exception :cljs :default) e
                    (throw (err/ex ::err/mst-projector-network-error
                                   (str "network error calling " nsid ": " (ex-message e))
                                   {:nsid nsid}))))
        status (:status resp)]
    (cond
      (>= status 500)
      (throw (err/ex ::err/mst-projector-server-error
                     (str nsid " HTTP " status ": " (subs200 (:body resp)))
                     {:nsid nsid :status status}))
      (>= status 400)
      (let [bj (try #?(:clj (json/parse-string (:body resp) true) :cljs nil)
                    (catch #?(:clj Exception :cljs :default) _
                      {:raw (subs200 (:body resp))}))]
        (throw (err/ex ::err/mst-projector-error
                       (str nsid " HTTP " status ": " bj)
                       {:nsid nsid :status status :body bj})))
      :else
      #?(:clj (json/parse-string (:body resp) true) :cljs (throw (ex-info "cljs json" {}))))))

;; ─── Public API ──────────────────────────────────────────────────────

(defn query-by-collection
  "Query all records in *collection*. opts: :limit (default 50), :cursor (omitted when nil).
  Returns {:records [...] :cursor str|nil}."
  [collection & {:keys [limit cursor] :or {limit 50}}]
  (call* "com.etzhayyim.mstProjector.queryByCollection"
         (cond-> {"collection" collection "limit" limit}
           (some? cursor) (assoc "cursor" cursor))))

(defn query-by-did
  "Query records authored by *did*, optionally filtered to :collection. opts: :collection
  (omitted when nil/blank — python `if collection:`), :limit (default 50), :cursor.
  Returns {:records [...] :cursor str|nil}."
  [did & {:keys [collection limit cursor] :or {limit 50}}]
  (call* "com.etzhayyim.mstProjector.queryByDid"
         (cond-> {"did" did "limit" limit}
           (and collection (not= "" collection)) (assoc "collection" collection)
           (some? cursor) (assoc "cursor" cursor))))

(defn query-by-field
  "Query records in *collection* where field-name == field-value. opts: :limit (default 50).
  Wire keys are camelCase fieldName/fieldValue (python parity). Returns {:records [...]}."
  [collection field-name field-value & {:keys [limit] :or {limit 50}}]
  (call* "com.etzhayyim.mstProjector.queryByField"
         {"collection" collection
          "fieldName" field-name
          "fieldValue" field-value
          "limit" limit}))

(defn count-by-collection
  "Return the total record count for *collection*. Returns {:count int :asOf iso-string}."
  [collection]
  (call* "com.etzhayyim.mstProjector.countByCollection"
         {"collection" collection}))
