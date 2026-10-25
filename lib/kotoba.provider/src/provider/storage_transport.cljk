(ns provider.storage-transport
  "Production transport for the bounded storage capability kit (ADR 0028,
  `provider.storage`), backed by a real blocking
  `java.net.http.HttpClient` call to a host-configured durable key/value
  service. See docs/adr/0071-production-storage-transport-host-configured-kv-endpoint.md
  for the full design rationale; this docstring is the summary.

  This namespace does NOT define a new provider or a new capability, and does
  NOT modify `storage.cljc`. Every bound `storage.cljc` already enforces --
  bounded keys, bounded 65536-byte values, `:option i64` conditional versions
  validated before the transport is ever called, backend exceptions redacted
  to a generic typed error -- runs exactly as before, unchanged and
  un-weakened. This namespace builds the one thing every provider in this ADR
  chain has always deferred to the host (ADR 0028: 'The injected transport
  owns durability, quota enforcement, and atomic version checks'): a real
  synchronous `(fn [request] -> reply)` you pass as `:transport` to
  `provider.storage/provider`.

  ## Storage must not acquire ambient filesystem authority (ADR 0049,
  `resources/kotoba/lang/capability-kits/storage-v1.edn`'s own
  `:ambient-filesystem false`)

  Unlike a naive implementation that would reach for `java.io.File`/
  `clojure.java.io` and write bytes under some default location (e.g. the
  process's home directory), this namespace never touches the local
  filesystem at all. It follows the exact same 'host injects a real
  synchronous transport, this namespace never invents an ambient default'
  pattern ADR 0064 (LLM) and ADR 0066 (HTTP) already established: durability
  is delegated ENTIRELY to a durable key/value HTTP service the host
  operates and explicitly points this transport at via a REQUIRED `:endpoint`
  construction option (or the `KOTOBA_STORAGE_ENDPOINT` env var) -- there is
  no default endpoint baked in (unlike LLM's `murakumo-main`), because unlike
  LLM there is no repo-wide well-known storage backend to default to; forcing
  explicit host configuration is itself part of the 'no ambient authority'
  design, not an oversight.

  ## Wire shape -- a single fixed JSON-over-HTTPS operation, not a
  filesystem-shaped path per key

  A single fixed path (default `/storage/v1/transact`, overridable) is POSTed
  to for every operation; the operation, namespace, key, value, and
  conditional version all travel in a JSON request body, never in the URL
  path. This is a deliberate simplification versus (for example) encoding the
  key into a URL path segment: keys are guest-controlled bounded strings, and
  folding them into a path invites a whole class of percent-encoding/path-
  traversal edge cases (`../`, encoded slashes, etc.) that a fixed-path
  JSON-body design sidesteps entirely -- there is no path segment ever built
  from guest-controlled bytes.

  ## No guest-facing SSRF surface, unlike ADR 0066's HTTP transport

  `:storage/transact` has no guest-supplied destination at all --
  `storage-namespace` is fixed once per provider instance by the HOST at
  construction (`storage.cljc`'s own docstring: 'The namespace is host-owned
  and never supplied by guest code'), and this transport's own `:endpoint` is
  likewise fixed once by the host at construction. This makes storage's
  threat model like ADR 0064's LLM transport (one fixed, host-chosen
  destination) rather than ADR 0066's HTTP transport (an arbitrary
  guest-named destination bounded only by an allow-list) -- so this
  namespace has no redirect-revalidation loop, no destination-IP block, and
  no allow-list: there is exactly one destination, chosen entirely by the
  host, never by the guest.

  ## Fail-closed sanitization of the upstream reply

  `storage.cljc`'s own post-transport checks (`entry`'s `value/bounded-string!`
  on the value, `valid-version?` on the version) run OUTSIDE
  `invoke-transport`'s try/catch, exactly like `http.cljc`'s post-transport
  header/body checks (ADR 0066 point 3). An oversized value or an
  out-of-range/non-integer version in the upstream JSON response would
  otherwise throw an unhandled exception past that boundary. This namespace
  defends against that by truncating an oversized value to
  `storage/max-value-bytes` and, more conservatively, by turning an invalid
  version or current-version into an explicit non-retryable
  `:storage/invalid-response` typed error rather than fabricating a
  plausible-looking version number -- a wrong-but-plausible version could
  silently mask a real conditional-version conflict, which is a strictly
  worse failure mode than a typed, visible error.

  ## `:cljs` / nbb production transport (ADR 0119)

  nbb/Node has no built-in *synchronous* HTTP primitive. This namespace keeps
  the reference provider's synchronous `(fn [request] -> reply)` contract by
  running each `/storage/v1/transact` POST in a child `node` process via
  `child_process.spawnSync` (same pattern as ADR 0117 HTTP / ADR 0118 LLM).
  Required host-configured `:endpoint`, fixed-path JSON wire, fail-closed
  sanitization, and typed HTTP errors match the `:clj` transport (ADR 0071)."
  (:require [kotoba.lang.text :as string]
            [provider.storage :as storage]
            [kotoba.kir.value :as value]
            #?(:clj [json.data-json :as json]))
  #?(:clj
     (:import (java.net URI)
              (java.net.http HttpClient HttpClient$Version HttpRequest
                             HttpRequest$BodyPublishers HttpResponse
                             HttpResponse$BodyHandlers)
              (java.time Duration))))

(def default-path
  "Fixed request path for every operation -- see ns docstring for why the
  key/namespace never appear in the URL path itself."
  "/storage/v1/transact")

(def default-connect-timeout-ms 5000)
(def default-request-timeout-ms 10000)

(def env-endpoint-var "KOTOBA_STORAGE_ENDPOINT")
(def env-api-key-var "KOTOBA_STORAGE_API_KEY")

;; A small headroom over storage/max-value-bytes for the JSON envelope
;; (quoting, escaping, the tag/version/key fields) around the value itself --
;; bounds how much this namespace will ever buffer for one response body,
;; independent of whatever `storage.cljc`'s own bounded-string! check does
;; afterward.
(def response-byte-limit (+ storage/max-value-bytes 8192))

;; ---------------------------------------------------------------------------
;; env / option resolution -- intentionally duplicated small helper, same
;; shape as llm-transport.cljc's and http-transport.cljc's own `getenv` (each
;; is `defn-`, not shared, to keep each transport namespace independently
;; readable -- see those namespaces' own comments for the same rationale).
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- getenv [name]
     (let [v (System/getenv name)]
       (when (and v (seq (string/trim v))) v))))

#?(:cljs
   (defn- getenv [name]
     (let [v (aget js/process.env name)]
       (when (and v (seq (string/trim v))) v))))

(defn resolve-endpoint
  "Resolve the fixed, host-configured storage-backend origin: an explicit
  `:endpoint` construction option, else the `KOTOBA_STORAGE_ENDPOINT` env
  var, else throws. There is deliberately no baked-in default (unlike LLM's
  `murakumo-main`) -- see ns docstring's 'ambient filesystem authority'
  section for why forcing explicit configuration here is itself part of this
  namespace's safety design, not an oversight."
  [opts]
  (or (:endpoint opts)
      (getenv env-endpoint-var)
      (throw (ex-info
              (str "storage-transport requires an :endpoint construction option (or "
                   env-endpoint-var
                   " env var) -- there is no repo-wide well-known storage backend to "
                   "default to, so the destination must be explicitly host-configured")
              {:phase :storage-transport}))))

(defn mem-transport
  "In-memory storage transport for tests + audit-hook demos (ADR 0271).

  Not durable and not a production backend. Optional `:on-call` receives
  `{:kit :storage :namespace :operation :key :reply-tag}` after each op
  (same optional audit surface as `production-transport`). Exceptions from
  on-call are swallowed.

  Store is a map of key → `{:value string :version long}`."
  ([] (mem-transport {}))
  ([{:keys [initial on-call]
     :or {initial {} on-call (fn [_])}}]
   (let [st (atom (into {} initial))
         audit! (fn [e]
                  (try (on-call e)
                       (catch #?(:clj Exception :cljs :default) _ nil)))]
     (fn [{:keys [namespace operation key value expected-version]}]
       (let [reply
             (case operation
               :get
               (if-let [e (get @st key)]
                 {:tag :found :key key :value (:value e) :version (:version e)}
                 {:tag :missing})
               :put
               (let [cur (get @st key)
                     cur-v (when cur (:version cur))]
                 (if (and (some? expected-version)
                          (not= expected-version cur-v))
                   {:tag :conflict :current-version cur-v}
                   (let [nv (inc (long (or cur-v 0)))]
                     (swap! st assoc key {:value (str value) :version nv})
                     {:tag :written :key key :value (str value) :version nv})))
               :delete
               (let [cur (get @st key)
                     cur-v (when cur (:version cur))]
                 (if (and (some? expected-version)
                          (not= expected-version cur-v))
                   {:tag :conflict :current-version cur-v}
                   (do (swap! st dissoc key)
                       {:tag :deleted})))
               {:tag :error
                :error {:code :storage/unsupported
                        :message "unknown op"
                        :retryable false}})]
         (audit! {:kit :storage
                  :namespace namespace
                  :operation operation
                  :key key
                  :reply-tag (:tag reply)})
         reply)))))

;; ---------------------------------------------------------------------------
;; keyword <-> wire string -- never used to build a URL path (see ns
;; docstring); only ever a JSON string value.
;; ---------------------------------------------------------------------------

(defn- kw->wire [kw]
  (if-let [ns (namespace kw)]
    (str ns "/" (name kw))
    (name kw)))

;; ---------------------------------------------------------------------------
;; request body
;; ---------------------------------------------------------------------------

(defn- request-body
  [{:keys [namespace operation key value expected-version]}]
  (cond-> {"namespace" (kw->wire namespace)
           "operation" (name operation)
           "key" (kw->wire key)}
    (= operation :put) (assoc "value" value)
    (contains? #{:put :delete} operation) (assoc "expected_version" expected-version)))

;; ---------------------------------------------------------------------------
;; bounded response body decoding -- defends `storage.cljc`'s own
;; post-transport `entry`/`option-version` checks (outside
;; `invoke-transport`'s try/catch) from an unhandled exception, exactly like
;; ADR 0066's `read-bounded-bytes`/`truncate-to-byte-limit` do for `http.cljc`.
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- read-bounded-bytes
     ^bytes [^java.io.InputStream in ^long max-bytes]
     (let [out (java.io.ByteArrayOutputStream.)
           buf (byte-array (int (min max-bytes 8192)))]
       (loop [total 0]
         (if (>= total max-bytes)
           (.toByteArray out)
           (let [to-read (int (min (alength buf) (- max-bytes total)))
                 n (.read in buf 0 to-read)]
             (if (neg? n)
               (.toByteArray out)
               (do (.write out buf 0 n)
                   (recur (+ total n))))))))))

(defn- truncate-to-byte-limit
  "Trims `s` until its own re-encoded UTF-8 byte count is `<= limit`. See
  http-transport.cljc's identically-named helper for why this loop (rather
  than a raw-byte substring) is the safe way to shrink a string that may have
  been decoded from truncated raw bytes."
  [s limit]
  (loop [s s]
    (if (<= (value/utf8-byte-count! s) limit)
      s
      (recur (subs s 0 (max 0 (dec (count s))))))))

#?(:clj
   (defn- decode-bounded-body [^bytes raw]
     (truncate-to-byte-limit (String. raw java.nio.charset.StandardCharsets/UTF_8)
                              response-byte-limit)))

;; ---------------------------------------------------------------------------
;; wire reply -> the {:tag ...} shape provider.storage's
;; `typed-result` expects. `key` is intentionally NOT part of the wire reply
;; -- `typed-result` already has it from the original request, so there is no
;; need for the wire protocol to echo it back (see ns docstring).
;; ---------------------------------------------------------------------------

(defn- sanitize-value
  "Bounds an upstream `value` to `storage/max-value-bytes`, coercing a
  non-string to its `str` form defensively (never throws)."
  [v]
  (truncate-to-byte-limit (str v) storage/max-value-bytes))

(defn- valid-version-number? [v]
  (and (integer? v) (<= 1 v)))

(defn- invalid-response-error [message]
  {:tag :error
   :error {:code :storage/invalid-response :message message :retryable false}})

(defn- finalize-reply
  "Final fail-closed sanitization pass over an already-tag-dispatched wire
  reply -- see ns docstring's 'Fail-closed sanitization' section. Never
  throws; a malformed value/version becomes a typed, non-retryable error
  instead of an uncaught exception past `storage.cljc`'s own boundary."
  [reply]
  (case (:tag reply)
    (:found :written)
    (let [{:keys [value version]} reply]
      (if (and (string? value) (valid-version-number? version))
        (update reply :value sanitize-value)
        (invalid-response-error
         "storage transport returned a malformed value/version for found/written")))

    :conflict
    (let [current-version (:current-version reply)]
      (if (or (nil? current-version) (valid-version-number? current-version))
        reply
        (invalid-response-error
         "storage transport returned a malformed current-version for conflict")))

    reply))

(defn- bounded-error-code
  "Coerces an upstream error code to a keyword whose UTF-8 byte length fits
  `value/keyword-value-byte-limit`, never throws. `storage.cljc`'s own
  `error` function re-validates this with `value/bounded-keyword!` OUTSIDE
  `invoke-transport`'s try/catch, so an oversized upstream code string would
  otherwise throw past that boundary exactly like an oversized value would."
  [code]
  (let [text (truncate-to-byte-limit (str code) value/keyword-value-byte-limit)]
    (if (seq text) (keyword text) :storage/upstream-error)))

(defn- wire->reply
  [parsed]
  (let [tag (keyword (str (:tag parsed)))]
    (finalize-reply
     (case tag
       :found {:tag :found :value (:value parsed) :version (:version parsed)}
       :missing {:tag :missing}
       :written {:tag :written :value (:value parsed) :version (:version parsed)}
       :deleted {:tag :deleted}
       :conflict {:tag :conflict :current-version (:current_version parsed)}
       :error {:tag :error
               :error {:code (bounded-error-code (get-in parsed [:error :code]))
                       :message (truncate-to-byte-limit
                                 (str (get-in parsed [:error :message] ""))
                                 value/string-value-byte-limit)
                       :retryable (boolean (get-in parsed [:error :retryable]))}}
       (throw (ex-info "storage transport received an unknown wire tag"
                       {:phase :storage-transport :tag tag}))))))

;; ---------------------------------------------------------------------------
;; non-2xx HTTP status -> a typed {:tag :error ...} reply, same status-code
;; taxonomy as ADR 0064's LLM transport (`error-for-status`).
;; ---------------------------------------------------------------------------

(defn- truncate-for-error-message [s limit]
  (let [s (str s)]
    (if (> (count s) limit) (str (subs s 0 limit) "...") s)))

(defn- error-for-status [status body]
  (let [retryable? (or (= status 429) (>= status 500))
        code (case (int status)
               429 :storage/rate-limited
               401 :storage/unauthorized
               403 :storage/forbidden
               404 :storage/not-found
               (if (>= status 500) :storage/upstream-error :storage/request-rejected))]
    {:tag :error
     :error {:code code
             :message (str "storage transport HTTP " status ": "
                           (truncate-for-error-message body 400))
             :retryable retryable?}}))

;; ---------------------------------------------------------------------------
;; wire I/O
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- send-transact-request
     [^HttpClient http-client
      {:keys [endpoint path api-key request-timeout-ms]}
      body-json]
     (let [url (str endpoint path)
           builder (-> (HttpRequest/newBuilder (URI/create url))
                      (.timeout (Duration/ofMillis (long request-timeout-ms)))
                      (.header "content-type" "application/json")
                      (.header "accept" "application/json")
                      (.POST (HttpRequest$BodyPublishers/ofString body-json)))
           builder (if api-key (.header builder "authorization" (str "Bearer " api-key)) builder)
           req (.build builder)
           resp (.send http-client req (HttpResponse$BodyHandlers/ofInputStream))
           status (.statusCode resp)
           ^java.io.InputStream in (.body resp)
           raw (try (read-bounded-bytes in response-byte-limit)
                    (finally (.close in)))]
       {:status status :body (decode-bounded-body raw)})))

;; ---------------------------------------------------------------------------
;; public constructor
;; ---------------------------------------------------------------------------

#?(:clj
   (defn production-transport
     "Build a synchronous transport fn for
     `(provider.storage/provider {:transport (production-transport ...) :storage-namespace ...})`.

     Input (already bounds-checked and admitted by `storage.cljc` before this
     fn ever runs): `{:namespace <qualified-kw> :operation <:get|:put|:delete>
     :key <kw> :value <string, :put only> :expected-version <int-or-nil,
     :put/:delete only>}`.

     Output: a `{:tag <keyword> ...}` map matching what
     `provider.storage`'s `typed-result` dispatches on
     (`:found`/`:missing`/`:written`/`:deleted`/`:conflict`/`:error`), or a
     `{:tag :error ...}` reply itself for a non-2xx HTTP status or a
     malformed upstream body (see `finalize-reply`). Network/IO exceptions
     (DNS failure, connection refused, timeout) are deliberately NOT caught
     here -- they propagate to
     `provider.storage/invoke-transport`'s own catch, which
     redacts them into a generic `:storage/transport` error, exactly like
     ADR 0064/0066's transports leave their own network exceptions uncaught
     for the same reason.

     Options:
       :endpoint -- REQUIRED (or the `KOTOBA_STORAGE_ENDPOINT` env var). The
         host-operated durable key/value service's origin, e.g.
         \"https://storage.internal.example\". See ns docstring's 'ambient
         filesystem authority' section for why there is no default.
       :path -- default `default-path`.
       :api-key -- optional bearer token (also `KOTOBA_STORAGE_API_KEY` env
         var).
       :connect-timeout-ms / :request-timeout-ms
       :on-call -- optional `(fn [event-map])` audit/observability hook,
         invoked after every attempt with `{:namespace :operation :key
         :status :http-status :latency-ms}` (`:status` is `:ok` or
         `:http-error`). Exceptions raised by this hook are swallowed and
         never affect the storage call -- additive, matching ADR 0064/0066's
         own `:on-call` rationale (no capability kit in this repo mandates
         quota/audit wiring at this layer today)."
     ([] (production-transport {}))
     ([opts]
      (let [endpoint (resolve-endpoint opts)
            path (:path opts default-path)
            api-key (or (:api-key opts) (getenv env-api-key-var))
            connect-timeout-ms (:connect-timeout-ms opts default-connect-timeout-ms)
            request-timeout-ms (:request-timeout-ms opts default-request-timeout-ms)
            on-call (:on-call opts (fn [_]))
            http-client (-> (HttpClient/newBuilder)
                            ;; Pin HTTP/1.1 explicitly -- same reason as ADR
                            ;; 0064/0066: a plain HTTP/1.1-only server
                            ;; (including this namespace's own
                            ;; `com.sun.net.httpserver` test fakes) cannot
                            ;; negotiate the JDK's default HTTP/2 attempt.
                            (.version HttpClient$Version/HTTP_1_1)
                            (.connectTimeout (Duration/ofMillis (long connect-timeout-ms)))
                            (.build))]
        (fn [{:keys [namespace operation key value expected-version] :as request}]
          (let [started (System/currentTimeMillis)
                safe-audit! (fn [event] (try (on-call event) (catch Exception _ nil)))
                body-json (json/write-str (request-body request))
                {:keys [status body]}
                (send-transact-request http-client
                                        {:endpoint endpoint :path path :api-key api-key
                                         :request-timeout-ms request-timeout-ms}
                                        body-json)
                latency-ms (- (System/currentTimeMillis) started)]
            (if (= 200 status)
              (let [parsed (json/read-str body :key-fn keyword)
                    reply (wire->reply parsed)]
                (safe-audit! {:namespace namespace :operation operation :key key
                              :status :ok :http-status status :latency-ms latency-ms})
                reply)
              (do
                (safe-audit! {:namespace namespace :operation operation :key key
                              :status :http-error :http-status status :latency-ms latency-ms})
                (error-for-status status body)))))))))

#?(:cljs
   (def ^:private node-http-script
     "One-shot HTTP POST. stdin JSON: {url, headers, body, timeoutMs}
      stdout JSON: {status, body} | {error:true, message}"
     (str
      "const https=require('https');const http=require('http');const {URL}=require('url');\n"
      "const MAX_BODY=73728;\n"
      "let raw='';process.stdin.setEncoding('utf8');\n"
      "process.stdin.on('data',c=>raw+=c);process.stdin.on('end',()=>{\n"
      "  try{\n"
      "    const req=JSON.parse(raw);\n"
      "    const u=new URL(req.url);\n"
      "    const lib=u.protocol==='https:'?https:http;\n"
      "    const headers=Object.assign({},req.headers||{});\n"
      "    const bodyBuf=Buffer.from(String(req.body||''),'utf8');\n"
      "    headers['content-length']=String(bodyBuf.length);\n"
      "    const opts={method:'POST',hostname:u.hostname,"
      "port:u.port||(u.protocol==='https:'?443:80),"
      "path:u.pathname+u.search,headers,timeout:Number(req.timeoutMs)||10000};\n"
      "    const r=lib.request(opts,res=>{\n"
      "      const chunks=[];let n=0;\n"
      "      res.on('data',c=>{if(n<MAX_BODY){const take=c.slice(0,MAX_BODY-n);chunks.push(take);n+=take.length;}});\n"
      "      res.on('end',()=>{\n"
      "        process.stdout.write(JSON.stringify({status:res.statusCode,"
      "body:Buffer.concat(chunks).toString('utf8')}));process.exit(0);\n"
      "      });\n"
      "    });\n"
      "    r.on('timeout',()=>{r.destroy();process.stdout.write(JSON.stringify("
      "{error:true,message:'timeout'}));process.exit(0);});\n"
      "    r.on('error',e=>{process.stdout.write(JSON.stringify("
      "{error:true,message:String(e&&e.message||e)}));process.exit(0);});\n"
      "    r.write(bodyBuf);r.end();\n"
      "  }catch(e){process.stdout.write(JSON.stringify({error:true,message:String(e)}));process.exit(0);}\n"
      "});\n")))

#?(:cljs
   (defn- node-http-post
     "Synchronous POST via spawnSync. Returns {:status n :body s}."
     [{:keys [url headers body timeout-ms]}]
     (let [child (js/require "child_process")
           payload (js/JSON.stringify
                    (clj->js {:url url
                              :headers (or headers {})
                              :body body
                              :timeoutMs (or timeout-ms default-request-timeout-ms)}))
           wall (+ (long (or timeout-ms default-request-timeout-ms)) 5000)
           result (.spawnSync child js/process.execPath
                              #js ["-e" node-http-script]
                              #js {:input payload :encoding "utf8" :timeout wall})]
       (try
         (let [parsed (js->clj (js/JSON.parse (or (.-stdout result) "{}"))
                               :keywordize-keys true)]
           (if (:error parsed)
             {:status 0 :body (str (:message parsed))}
             {:status (:status parsed)
              :body (truncate-to-byte-limit (str (:body parsed)) response-byte-limit)}))
         (catch :default e
           {:status 0 :body (str "transport decode failed: " (.-message e))})))))

#?(:cljs
   (defn- send-transact-request
     [{:keys [endpoint path api-key request-timeout-ms]} body-json]
     (let [url (str endpoint path)
           headers (cond-> {"content-type" "application/json"
                            "accept" "application/json"}
                     api-key (assoc "authorization" (str "Bearer " api-key)))]
       (node-http-post {:url url :headers headers :body body-json
                        :timeout-ms request-timeout-ms}))))

#?(:cljs
   (defn production-transport
     "Build a synchronous transport fn for nbb/cljs Node hosts (ADR 0119).

     Uses `child_process.spawnSync` + a one-shot Node HTTP script so the
     reference provider's `(fn [request] -> reply)` contract stays
     synchronous. Required host-configured `:endpoint`, fixed-path JSON wire,
     fail-closed sanitization, and typed HTTP errors match the `:clj`
     transport (ADR 0071).

     Options: same as `:clj` — `:endpoint` (required), `:path`, `:api-key`,
     `:connect-timeout-ms`, `:request-timeout-ms`, `:on-call`."
     ([] (production-transport {}))
     ([opts]
      (let [endpoint (resolve-endpoint opts)
            path (:path opts default-path)
            api-key (or (:api-key opts) (getenv env-api-key-var))
            request-timeout-ms (:request-timeout-ms opts default-request-timeout-ms)
            on-call (:on-call opts (fn [_]))]
        (fn [{:keys [namespace operation key value expected-version] :as request}]
          (let [started (js/Date.now)
                safe-audit! (fn [event] (try (on-call event) (catch :default _ nil)))
                body-json (js/JSON.stringify (clj->js (request-body request)))
                {:keys [status body]}
                (send-transact-request
                 {:endpoint endpoint :path path :api-key api-key
                  :request-timeout-ms request-timeout-ms}
                 body-json)
                latency-ms (- (js/Date.now) started)]
            (if (= 200 status)
              (try
                (let [parsed (js->clj (js/JSON.parse body) :keywordize-keys true)
                      reply (wire->reply parsed)]
                  (safe-audit! {:namespace namespace :operation operation :key key
                                :status :ok :http-status status :latency-ms latency-ms})
                  reply)
                (catch :default e
                  (safe-audit! {:namespace namespace :operation operation :key key
                                :status :http-error :http-status status :latency-ms latency-ms})
                  (invalid-response-error
                   (str "storage transport reply decode failed: " (.-message e)))))
              (do
                (safe-audit! {:namespace namespace :operation operation :key key
                              :status :http-error :http-status status :latency-ms latency-ms})
                (error-for-status (or status 0) (or body ""))))))))))
