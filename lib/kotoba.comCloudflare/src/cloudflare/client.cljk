(ns cloudflare.client
  "Portable core for talking to the Cloudflare API v4 -- REST and GraphQL
  Analytics, one auth/HTTP boundary for every cloudflare.* namespace in
  this library.

  Extracted from cloud-itonami.analytics (gftdcojp/cloud-itonami,
  ADR-0010/0012), which had grown its own ad hoc, itonami-specific copy of
  this exact query-building/HTTP-call pattern. This library generalizes it
  (no itonami-specific defaults) so any project needing Cloudflare zone/
  worker/analytics access can depend on one tested client instead of
  re-deriving it.

  Query construction and response parsing are pure .cljc. The actual HTTP
  call is JVM-only by default (java.net.http) but always takes an
  injectable `:http-fn` -- the same `{:url :method :headers :body} ->
  {:status :body}` convention used throughout kotoba-lang/gftdcojp's other
  HTTP-calling namespaces (cloud-itonami.runtime/jvm-http-fn,
  cloud-itonami.mail/jvm-http-fn) -- so every namespace here is testable
  with a stub, never only against a live account.

  W6 product-shell + T6.4: pure URL/auth helpers require the shipped
  `:client` KIR on every platform. Host pure mirrors are gone — cljs/nbb
  must preload shipped KIR (resources/ via nbb cwd, register-kir!, or
  set-resource-loader!) before requiring this ns (ADR-0016).
  HTTP/JSON/getenv stay host."
  (:require [kotoba.lang.text :as str]
            #?(:clj [json.data-json :as json])
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :client)

(defn- o
  "Call a pure export. Requires the shipped oracle on every platform (T6.4)."
  [export args]
  (oracle/require-ready! oid)
  (oracle/call oid export args))

(defn- o-record
  "T5.2: structural host map → call-record (requires shipped oracle)."
  [export host-map field-specs]
  (oracle/require-ready! oid)
  (oracle/call-record oid export host-map field-specs))

(def api-base
  (o 'api-base []))

(def graphql-endpoint
  (o 'graphql-endpoint []))

#?(:clj
(defn jvm-http-fn
  "Real java.net.http transport. {:url :method :headers :body} ->
  {:status :body}, same convention as cloud-itonami.runtime/jvm-http-fn."
  ([] (jvm-http-fn {}))
  ([{:keys [timeout-seconds] :or {timeout-seconds 30}}]
   (fn [{:keys [url method headers body]}]
     (let [builder (-> (java.net.http.HttpRequest/newBuilder (java.net.URI/create url))
                       (.timeout (java.time.Duration/ofSeconds timeout-seconds))
                       (as-> b (reduce-kv (fn [b k v] (.header b k v)) b headers)))
           request (case method
                     :post (-> builder
                              (.POST (java.net.http.HttpRequest$BodyPublishers/ofString (or body "")))
                              .build)
                     :put (-> builder
                             (.PUT (java.net.http.HttpRequest$BodyPublishers/ofString (or body "")))
                             .build)
                     :get (-> builder .GET .build)
                     :delete (-> builder .DELETE .build)
                     (throw (ex-info "Unsupported HTTP method" {:method method})))
           resp (.send (java.net.http.HttpClient/newHttpClient) request
                      (java.net.http.HttpResponse$BodyHandlers/ofString))]
       {:status (.statusCode resp) :body (.body resp)})))))

;; Named secret identity for W6 secret-custody kit (provider.secret id 21 /
;; secret-transport ADR 0145–0146). Hosts inject :fetch with the same reply
;; shape; default path reads only CLOUDFLARE_API_TOKEN by exact name.
(def api-token-secret-name
  (o 'api-token-secret-name []))

(def api-token-env-name
  (o 'api-token-env-name []))

(defn bearer-auth
  "Authorization header value. Kotoba `bearer-auth` (T6.4 requires oracle)."
  [token]
  (o-record 'bearer-auth {:token token} [[:token :string]]))

(def ^:private kv-schema
  "Guest :client/kv — T5.2 native record for query-pair."
  [:record :client/kv [[:k :string] [:v :string]]])

(def ^:private path-qs-schema
  "Guest :client/path-qs — T5.2 native record for with-query/rest-url."
  [:record :client/path-qs [[:path :string] [:qs :string]]])

(defn rest-url
  "Absolute REST URL for path + query string (no leading `?` in qs).
   Kotoba `rest-url` (T6.4 requires oracle). T5.2 native guest record."
  [path qs]
  (o-record 'rest-url
            {:in (oracle/record path-qs-schema {:path path :qs (or qs "")})}
            [[:in :raw]]))

(defn query-pair
  "One `k=v` query fragment. Kotoba `query-pair` (T6.4 requires oracle).
   T5.2 native guest record."
  [k v]
  (o-record 'query-pair
            {:in (oracle/record kv-schema {:k k :v v})}
            [[:in :raw]]))

(defn transport-ok?
  "True when HTTP status is a 2xx. Kotoba `transport-ok?` (T6.4 requires oracle)."
  [status]
  (= 1 (oracle/i64->host (o-record 'transport-ok? {:status status} [[:status :i64]]))))

(defn prefer-explicit-token?
  "True when a non-blank explicit token should win over fetch.
   Kotoba `prefer-explicit-token?` (T6.4 requires oracle)."
  [token]
  (= 1 (oracle/i64->host (o-record 'prefer-explicit-token? {:token token} [[:token :string]]))))

(defn secret-name-matches?
  "True when `name` is the api-token secret id.
   Kotoba `secret-name-matches?` (T6.4 requires oracle)."
  [name]
  (= 1 (oracle/i64->host (o-record 'secret-name-matches? {:name name} [[:name :string]]))))

#?(:clj
(defn env-token-fetch
  "Default host fetch transport: exact env var only (no process-env dump).

  Reply shape matches provider.secret-transport:
  `{:tag :value :value s}` | `{:tag :error :code :message}`."
  []
  (fn [{:keys [name]}]
    (if (secret-name-matches? name)
      (if-let [v (System/getenv api-token-env-name)]
        (if (str/blank? v)
          {:tag :error :code :secret/empty :message "CLOUDFLARE_API_TOKEN empty"}
          {:tag :value :value v})
        {:tag :error :code :secret/not-found :message "CLOUDFLARE_API_TOKEN not set"})
      {:tag :error :code :secret/not-found :message "no env mapping"}))))

#?(:clj
(defn api-token
  "Resolve the Cloudflare API token under the named-secret contract.

  Preference order:
  1. explicit `:token` string
  2. `:fetch` one-shot `(fn [{:keys [name]}] reply)` — kit-compatible;
     wire `provider.secret-transport/env-fetch`, `fn-fetch` (kagi), or
     `keychain-fetch` here
  3. default env-token-fetch (exact CLOUDFLARE_API_TOKEN only)

  Never enumerates process environment keys."
  ([] (api-token {}))
  ([{:keys [token fetch] :or {fetch (env-token-fetch)}}]
   (or (when (prefer-explicit-token? token) token)
       (let [reply (fetch {:name api-token-secret-name})]
         (when (and (map? reply) (= :value (:tag reply)))
           (let [v (str (:value reply))]
             (when-not (str/blank? v) v))))
       (throw (ex-info "CLOUDFLARE_API_TOKEN is required"
                       {:secret-name api-token-secret-name
                        :env-name api-token-env-name}))))))

#?(:clj
(defn- auth-headers
  ([token] (auth-headers token "application/json"))
  ([token content-type]
   (cond-> {"Authorization" (bearer-auth token)}
     content-type (assoc "Content-Type" content-type)))))

#?(:clj
(defn- resolve-token
  "Pick explicit :token or resolve via named-secret :fetch."
  [{:keys [token fetch] :as opts}]
  (or (when (prefer-explicit-token? token) token)
      (api-token (cond-> {} fetch (assoc :fetch fetch))))))

#?(:clj
(defn graphql!
  "POST `request-body` ({:query :variables}) to the Analytics GraphQL API.
  Returns the parsed JSON response ({:data ... :errors ...}), never
  throws on a GraphQL-level error (callers check :errors) -- only throws on
  a transport-level non-2xx HTTP status.

  Auth: `:token` string, or `:fetch` kit-shaped secret getter (see api-token)."
  ([request-body] (graphql! request-body {}))
  ([request-body {:keys [http-fn] :or {http-fn (jvm-http-fn)} :as opts}]
   (let [resp (http-fn {:url graphql-endpoint
                        :method :post
                        :headers (auth-headers (resolve-token opts))
                        :body (json/write-str request-body)})]
     (when-not (transport-ok? (:status resp))
       (throw (ex-info "Cloudflare GraphQL request failed" {:status (:status resp) :body (:body resp)})))
     (json/read-str (:body resp) :key-fn keyword)))))

#?(:clj
(defn rest!
  "Call a Cloudflare REST v4 endpoint. `path` is relative to api-base (e.g.
  \"/zones\" or (str \"/zones/\" zone-id \"/dns_records\")). Returns the
  parsed JSON response's :result on success; throws (with the full
  response) on a transport-level non-2xx status OR a Cloudflare-level
  {:success false} response -- REST errors are structural, unlike GraphQL's
  partial-success shape, so failing closed here is the safer default.

  Auth: `:token` string, or `:fetch` kit-shaped secret getter (see api-token)."
  ([path] (rest! path {}))
  ([path {:keys [method body http-fn query content-type raw-body?]
          :or {method :get http-fn (jvm-http-fn) content-type "application/json"}
          :as opts}]
   (let [qs (when (seq query)
              (str/join "&" (map (fn [[k v]] (query-pair (name k) v)) query)))
         url (rest-url path (or qs ""))
         ;; Deploy uploads may send raw JS (`raw-body?` true); default JSON-encodes maps.
         body-str (cond
                    (nil? body) nil
                    raw-body? (str body)
                    (string? body) body
                    :else (json/write-str body))
         ;; When content-type is application/javascript, treat string body as raw.
         body-str (if (and (string? body)
                           (not= content-type "application/json")
                           (not raw-body?))
                    (str body)
                    body-str)
         resp (http-fn (cond-> {:url url
                                :method method
                                :headers (auth-headers (resolve-token opts) content-type)}
                        body-str (assoc :body body-str)))
         parsed (json/read-str (:body resp) :key-fn keyword)]
     (when-not (and (transport-ok? (:status resp)) (:success parsed))
       (throw (ex-info "Cloudflare REST request failed"
                       {:status (:status resp) :path path :errors (:errors parsed)})))
     (:result parsed)))))
