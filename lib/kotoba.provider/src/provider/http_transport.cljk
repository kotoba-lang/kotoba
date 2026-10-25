(ns provider.http-transport
  "Production transport for the bounded HTTP capability kit (ADR 0026,
  `provider.http`), backed by a real blocking
  `java.net.http.HttpClient`. See
  docs/adr/0066-production-http-transport-bounded-redirect-following.md for
  the full design rationale; this docstring is the summary.

  This namespace does NOT define a new provider or a new capability, and does
  NOT modify `http.cljc`. Every bound `http.cljc` already enforces on the
  guest-facing request -- exact-origin allowlist, absolute-HTTPS-only, no
  fragments, header-count/size/body/timeout bounds -- runs exactly as before,
  unchanged and un-weakened, before this transport is ever invoked. This
  namespace builds the one thing every provider in this ADR chain has always
  deferred to the host (ADR 0026: 'Production hosts may implement deadlines
  and I/O outside the guest, but must return the same bounded result'): a
  real synchronous `(fn [request] -> reply)` you pass as `:transport` to
  `provider.http/provider`.

  ## SSRF is the primary threat model here, not an afterthought

  ADR 0064's LLM transport always calls ONE fixed, host-chosen endpoint.
  `:http/post` calls whatever HTTPS origin the GUEST names, bounded only by
  the host's own closed `allowed-origins` set -- so, unlike the LLM
  transport, this is a genuine server-side-request-forgery surface. Three
  defenses this namespace adds ON TOP OF (never in place of) `http.cljc`'s
  own bounds:

  1. **Redirects are never auto-followed by the JDK.** The `HttpClient` is
     built with `HttpClient$Redirect/NEVER`; THIS namespace owns the redirect
     loop instead, and re-validates EVERY hop's resolved origin against the
     exact same closed `allowed-origins` set the host also gave to
     `http/provider` (a required constructor option here, not optional, and
     it must be the identical set) before following it -- matching the
     capability kit's own already-declared semantics
     (`resources/kotoba/lang/capability-kits/http-v1.edn`:
     `:redirects :transport-must-not-follow-outside-allowlist`). A redirect
     whose target origin is not in the allow-list, or that would exceed
     `:max-redirects` (default 5), is simply NOT followed -- the 3xx
     response is returned to the guest as an ordinary typed `:ok` response
     (never silently swallowed, never a thrown exception) so the guest or
     its host can decide whether to issue a fresh, independently-bounded
     `:http/post` call of its own.
  2. **A best-effort private/loopback/link-local/multicast destination-IP
     block runs before every hop's actual connection**
     (`InetAddress/getAllByName` -> reject if ANY resolved address is
     loopback, link-local, RFC1918/site-local, IPv6 unique-local
     (`fc00::/7`), multicast, or any-local/wildcard). This is explicitly NOT
     a complete DNS-rebinding defense -- see `destination-blocked?` and
     docs/adr/0066 'Remaining gaps': the address checked here is not pinned
     for the actual `HttpClient.send` connection that follows, so a TOCTOU
     race against attacker-controlled DNS with a very short TTL is not fully
     closed by this check alone.
  3. **The response body is read through a length-bounded stream reader**
     (never `BodyHandlers/ofByteArray`'s fully-unbounded in-memory buffer),
     and every response header is folded to a bounded count/size before
     being handed back to `http.cljc`. Both defend `http.cljc`'s own
     post-transport checks (`value/bounded-string!` on the body,
     `typed-headers` on the header set) -- which run OUTSIDE
     `invoke-transport`'s try/catch -- from throwing an unhandled exception
     on an ordinary large-body or many-header real-world response, which
     would otherwise violate ADR 0026's own invariant that 'the guest never
     receives a connection, stream, promise, or host exception'.

  ## `:cljs` / nbb production transport (ADR 0117)

  nbb/Node has no built-in *synchronous* HTTP primitive (`fetch` is
  Promise-based). This namespace keeps the reference provider's synchronous
  `(fn [request] -> reply)` contract by running each hop in a child
  `node` process via `child_process.spawnSync` (the same blocking-subprocess
  pattern this monorepo already uses for conformance launchers). The
  redirect loop, allow-list revalidation, and connect-refusal asymmetry
  stay in portable cljs so they match the `:clj` loop's structure and
  remain unit-testable with `with-redefs`. Destination-IP blocking on
  `:cljs` resolves hostnames through the same child (`dns.lookup`); IP
  literals are checked without DNS. DNS-rebinding TOCTOU remains an
  explicit remaining gap (same honesty as ADR 0066's `:clj` path)."
  (:require [kotoba.lang.text :as string]
            [provider.http :as http]
            [kotoba.kir.value :as value])
  #?(:clj
     (:import (java.net InetAddress URI URISyntaxException UnknownHostException)
              (java.net.http HttpClient HttpClient$Version HttpClient$Redirect
                             HttpRequest HttpRequest$Builder
                             HttpRequest$BodyPublishers
                             HttpResponse HttpResponse$BodyHandlers)
              (java.io ByteArrayOutputStream InputStream)
              (java.nio.charset StandardCharsets)
              (java.time Duration))))

(def default-connect-timeout-ms
  "HttpClient-level TCP connect timeout. Independent of the guest-supplied
  per-request `timeout-ms` (which bounds each hop's whole request/response
  cycle via `HttpRequest.Builder/timeout`, enforced already by `http.cljc`
  to be within `[1, http/max-timeout-ms]`)."
  5000)

(def default-max-redirects
  "How many redirect hops this namespace's own loop will follow before
  giving up and returning the last 3xx response as-is. `0` disables
  redirect-following entirely (every 3xx is returned immediately). Bounded
  small on purpose: worst-case wall-clock time for one guest `:http/post`
  call is bounded by `(inc max-redirects) * timeout-ms`, so this value
  directly controls how much that can multiply the guest's own bounded
  per-call timeout."
  5)

(def restricted-header-names
  "Header names `java.net.http.HttpRequest.Builder/header` refuses to set
  itself (a JDK client restriction, not a Kotoba bound). Dropped
  defensively before building the outbound request so a guest that
  happens to set one of these degrades quietly -- the header is simply not
  forwarded -- instead of the whole call failing with an opaque
  `IllegalArgumentException` thrown from deep inside the JDK client (which
  would still be caught and typed by `http.cljc`'s `invoke-transport`, but
  with no useful information)."
  #{"connection" "content-length" "expect" "host" "upgrade"})

;; ---------------------------------------------------------------------------
;; origin canonicalization -- intentionally duplicated from
;; `provider.http`'s private `https-origin` (that fn is
;; `defn-`, not exported, and this namespace needs a non-throwing predicate
;; form for the redirect loop). Keep the regex in sync if `http.cljc`'s ever
;; changes -- see docs/adr/0066 for why this is a deliberate duplication
;; rather than reaching into `http.cljc`'s private var.
;; ---------------------------------------------------------------------------

(def origin-pattern
  #"https://([A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)(?::([0-9]+))?(?:/[^ ]*)?")

(defn canonical-origin
  "Returns the canonical `\"https://host[:port]\"` origin for `url`, or nil
  if it is not an absolute HTTPS URL, carries a fragment, or otherwise fails
  to parse -- never throws. Mirrors `http.cljc`'s own `https-origin`
  acceptance rule exactly (same regex, same lower-cased host) so a set of
  origins already validated as canonical by `http/provider` also validates
  identically here."
  [url]
  (when (and (string? url) (not (string/includes? url "#")))
    (when-let [[_ host port] (re-matches origin-pattern url)]
      (str "https://" (string/lower host) (when port (str ":" port))))))

;; ---------------------------------------------------------------------------
;; destination-IP check (best-effort; see ns docstring point 2 and
;; docs/adr/0066 Remaining gaps for what this does NOT close)
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- unique-local-ipv6?
     "`fc00::/7` -- IPv6 unique-local addresses. `InetAddress/isSiteLocalAddress`
     only recognizes the deprecated `fec0::/10` IPv6 site-local range, not
     this one, so it needs its own check."
     [^InetAddress addr]
     (and (instance? java.net.Inet6Address addr)
          (let [b (.getAddress addr)]
            (= 0xfc (bit-and (int (aget ^bytes b 0)) 0xfe))))))

#?(:clj
   (defn- private-address?
     [^InetAddress addr]
     (or (.isLoopbackAddress addr)
         (.isLinkLocalAddress addr)
         (.isSiteLocalAddress addr)
         (.isMulticastAddress addr)
         (.isAnyLocalAddress addr)
         (unique-local-ipv6? addr))))

#?(:clj
   (defn- destination-blocked?
     "Resolve `host` and reject if ANY returned address is loopback,
     link-local, RFC1918/site-local, IPv6 unique-local, multicast, or
     any-local/wildcard. Returns false (not blocked) on a DNS resolution
     failure -- that is an ordinary network error the actual connection
     attempt will raise on its own moments later, propagating to
     `http.cljc`'s `invoke-transport` catch-all exactly like any other
     connect failure; this predicate does not need to duplicate that path."
     [^String host]
     (try
       (boolean (some private-address? (InetAddress/getAllByName host)))
       (catch UnknownHostException _ false))))

;; ---------------------------------------------------------------------------
;; bounded response decoding -- defends `http.cljc`'s own post-transport
;; `value/bounded-string!` / `typed-headers` checks (outside
;; `invoke-transport`'s try/catch) from an unhandled exception on an
;; ordinary large-body or many-header real response.
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- read-bounded-bytes
     "Reads at most `max-bytes` from `in`, never buffering more than that in
     memory regardless of how large the real response body is."
     ^bytes [^InputStream in ^long max-bytes]
     (let [out (ByteArrayOutputStream.)
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
  "Trims `s` until its re-encoded UTF-8 byte count is `<= limit`. Shared by
  `:clj` (post-decode safety net) and `:cljs` (header/body folding)."
  [s limit]
  (loop [s s]
    (if (<= (value/utf8-byte-count! s) limit)
      s
      (recur (subs s 0 (max 0 (dec (count s))))))))

#?(:clj
   (defn- decode-bounded-body [^bytes raw]
     (truncate-to-byte-limit (String. raw StandardCharsets/UTF_8)
                              value/string-value-byte-limit)))

#?(:clj
   (defn- bounded-response-headers
     "Folds a real `java.net.http.HttpHeaders` down to the same shape
     `http.cljc`'s `typed-headers` requires: at most `http/max-headers`
     entries, each a keyword name within `value/keyword-value-byte-limit`
     bytes and a string value within `value/string-value-byte-limit` bytes.
     Known, documented lossy simplifications (see docs/adr/0066): header
     names are case-folded (so e.g. `Content-Type` and `content-type` from
     a misbehaving upstream would collide -- the second one wins, arbitrary
     order); when a name repeats only its FIRST value is kept (relevant to
     e.g. multiple `Set-Cookie` headers); and which headers survive the
     `max-headers` cap when a response has more than that is unspecified
     order, not guest-visible priority."
     [^java.net.http.HttpHeaders response-headers]
     (->> (.map response-headers)
          (keep (fn [[name values]]
                  (let [folded (string/lower name)]
                    (when (and (seq values)
                               (<= (value/utf8-byte-count! folded) value/keyword-value-byte-limit))
                      [(keyword folded)
                       (truncate-to-byte-limit (first values) value/string-value-byte-limit)]))))
          (take http/max-headers)
          (into {}))))

;; ---------------------------------------------------------------------------
;; per-hop request/response
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- send-hop
     "Issues one bounded synchronous POST to `uri` and returns the raw
     `HttpResponse<InputStream>` -- caller decides whether to follow (and
     discard/close the body) or finish (bounded-read the body and close)."
     ^HttpResponse [^HttpClient http-client ^URI uri headers body timeout-ms]
     (let [safe-headers (remove (fn [[k _]]
                                  (contains? restricted-header-names
                                             (string/lower (name k))))
                                headers)
           builder (-> (HttpRequest/newBuilder uri)
                      (.timeout (Duration/ofMillis (long timeout-ms))))
           ^HttpRequest$Builder builder
           (reduce (fn [^HttpRequest$Builder b [k v]]
                     (.header b (name k) v))
                   builder safe-headers)
           req (-> builder
                  (.POST (HttpRequest$BodyPublishers/ofString body))
                  (.build))]
       (.send http-client req (HttpResponse$BodyHandlers/ofInputStream)))))

#?(:clj
   (defn- send-hop-get
     "Bounded synchronous GET (no request body) for `:http/get-stream`
     (ADR 0128). Same header restriction and timeout wiring as `send-hop`."
     ^HttpResponse [^HttpClient http-client ^URI uri headers timeout-ms]
     (let [safe-headers (remove (fn [[k _]]
                                  (contains? restricted-header-names
                                             (string/lower (name k))))
                                headers)
           builder (-> (HttpRequest/newBuilder uri)
                       (.timeout (Duration/ofMillis (long timeout-ms)))
                       (.GET))
           ^HttpRequest$Builder builder
           (reduce (fn [^HttpRequest$Builder b [k v]]
                     (.header b (name k) v))
                   builder safe-headers)
           req (.build builder)]
       (.send http-client req (HttpResponse$BodyHandlers/ofInputStream)))))

#?(:clj
   (defn- finish!
     "Bounded-reads and closes the response body, and folds the response
     headers, producing the `{:status :headers :body}` shape
     `http.cljc`'s `:invoke` expects back from a successful transport call."
     [^HttpResponse resp]
     (let [status (.statusCode resp)
           response-headers (.headers resp)
           ^InputStream in (.body resp)
           raw (try (read-bounded-bytes in value/string-value-byte-limit)
                    (finally (.close in)))]
       {:status status
        :headers (bounded-response-headers response-headers)
        :body (decode-bounded-body raw)})))

#?(:clj
   (defn- finish-get-stream!
     "Bounded-read response body as host `:bytes` for get-stream (ADR 0128).
     Cap is `http/max-pull-bytes` (same as get-stream provider)."
     [^HttpResponse resp]
     (let [^InputStream in (.body resp)
           raw (try (read-bounded-bytes in (long http/max-pull-bytes))
                    (finally (.close in)))]
       {:bytes raw})))

#?(:clj
   (defn- redirect-target
     "Resolves `location` against `base-uri` and returns the resolved
     absolute URL string, or nil if it does not parse, exceeds
     `http/max-url-bytes`, or resolves to something other than an absolute
     HTTPS URL. Never throws."
     [^URI base-uri ^String location]
     (try
       (let [resolved (str (.resolve base-uri (URI. location)))]
         (when (<= (value/utf8-byte-count! resolved) http/max-url-bytes)
           resolved))
       (catch URISyntaxException _ nil)
       (catch IllegalArgumentException _ nil))))

#?(:clj
   (defn- connect-refusal-reason
     "nil if `url` is safe to connect to right now (its canonical origin is
     in `allowed-origins` AND its resolved host is not a blocked private/
     loopback/link-local/multicast destination); otherwise a keyword saying
     which check failed: `:not-in-allow-list` or `:destination-blocked`.
     Used both for the FIRST hop (where a non-nil reason means refuse the
     whole call with a typed error -- see `follow-and-collect!`) and for
     each candidate redirect target (where a non-nil reason means decline
     to follow, not error -- the prior response is returned as-is)."
     [url allowed-origins]
     (let [origin (canonical-origin url)]
       (cond
         (or (nil? origin) (not (contains? allowed-origins origin))) :not-in-allow-list
         (destination-blocked? (.getHost (URI/create url))) :destination-blocked
         :else nil))))

#?(:clj
   (defn- refusal-error [reason url]
     {:error {:code :http/destination-blocked
              :message (case reason
                         :destination-blocked
                         (str "resolved address for " (.getHost (URI/create url))
                              " is not an allowed destination"
                              " (loopback/link-local/private/multicast)")
                         :not-in-allow-list
                         (str "destination is outside the allowed-origins set: " url))
              :retryable false}}))

#?(:clj
   (defn- follow-and-collect!
     "The redirect loop.

     The FIRST hop -- the guest's own original URL, already validated once
     by `http.cljc`'s own `:invoke` before this transport ever runs -- is
     re-validated here too (defense in depth: this transport has no
     independent authority and must never trust a caller that skipped
     `http.cljc`). If it fails either check, this call refuses outright
     with a typed `:http/destination-blocked` error.

     Every SUBSEQUENT hop (a redirect target) is validated the same way
     BEFORE it is ever connected to, but a failure there is NOT an error --
     the prior response (the 3xx itself) is simply returned to the guest
     as-is, un-followed. Exceeding `max-redirects` is handled identically
     (the candidate is treated as absent, so the loop's last response
     becomes final). This is the one asymmetry in this namespace: refuse
     the call the guest actually asked for with a typed error, but never
     error out over a redirect this transport merely chose not to chase."
     [{:keys [http-client allowed-origins max-redirects]} initial-url headers body timeout-ms]
     (if-let [reason (connect-refusal-reason initial-url allowed-origins)]
       (refusal-error reason initial-url)
       (loop [current-url initial-url
              redirects-left max-redirects]
         (let [uri (URI/create current-url)
               resp (send-hop http-client uri headers body timeout-ms)
               status (.statusCode resp)
               location (some-> (.firstValue (.headers resp) "location")
                                (.orElse nil))
               candidate (when (and (<= 300 status 399) location (pos? redirects-left))
                          (redirect-target uri location))]
           (if (and candidate (nil? (connect-refusal-reason candidate allowed-origins)))
             (do (.close ^InputStream (.body resp))
                 (recur candidate (dec redirects-left)))
             (finish! resp)))))))

#?(:clj
   (defn- follow-and-collect-get!
     "Redirect loop for GET get-stream (ADR 0128). Same allow-list /
     destination asymmetry as `follow-and-collect!`, but the final body is
     raw host `:bytes` (not a UTF-8 string response record)."
     [{:keys [http-client allowed-origins max-redirects]} initial-url headers timeout-ms]
     (if-let [reason (connect-refusal-reason initial-url allowed-origins)]
       (refusal-error reason initial-url)
       (loop [current-url initial-url
              redirects-left max-redirects]
         (let [uri (URI/create current-url)
               resp (send-hop-get http-client uri headers timeout-ms)
               status (.statusCode resp)
               location (some-> (.firstValue (.headers resp) "location")
                                (.orElse nil))
               candidate (when (and (<= 300 status 399) location (pos? redirects-left))
                           (redirect-target uri location))]
           (if (and candidate (nil? (connect-refusal-reason candidate allowed-origins)))
             (do (.close ^InputStream (.body resp))
                 (recur candidate (dec redirects-left)))
             (finish-get-stream! resp)))))))

;; ---------------------------------------------------------------------------
;; public constructor
;; ---------------------------------------------------------------------------

#?(:clj
   (defn production-transport
     "Build a synchronous transport fn for
     `(provider.http/provider {:transport (production-transport ...) :allowed-origins ...})`.

     Input (already bounds-checked and admitted by `http.cljc` before this
     fn ever runs): `{:url <string> :headers {<keyword> <string>}
     :body <string> :timeout-ms <int>}`.

     Output: `{:status <int> :headers {<keyword> <string>} :body <string>}`
     on success (including a 3xx not followed for any reason -- see ns
     docstring), or `{:error {:code <keyword> :message <string>
     :retryable <bool>}}` when this namespace itself refuses to connect
     (destination-blocked). Network/IO exceptions (DNS failure, connection
     refused, timeout, TLS failure) are deliberately NOT caught here --
     they propagate to `provider.http/invoke-transport`'s
     own catch, which redacts them into a generic `:http/transport` error,
     exactly like ADR 0064's LLM transport leaves its own network
     exceptions uncaught for the same reason.

     Options:
       :allowed-origins -- REQUIRED. Must be the identical closed set of
         canonical `\"https://host[:port]\"` strings also given to
         `http/provider`'s own `:allowed-origins`. This namespace has no
         independent authority over destinations; it only ever re-checks
         the SAME allow-list on every redirect hop. There is deliberately
         no way to configure this transport with a wider or different
         allow-list than the provider's own -- that would silently
         reintroduce the exact SSRF surface ADR 0026 closed.
       :max-redirects -- default `default-max-redirects` (5). `0` disables
         redirect-following: every 3xx response is returned immediately.
       :connect-timeout-ms -- HttpClient-level TCP connect timeout, default
         `default-connect-timeout-ms`.
       :on-call -- optional `(fn [event-map])` audit/observability hook,
         invoked after every attempt with `{:url :status :error?
         :latency-ms}`. Exceptions raised by this hook are swallowed and
         never affect the HTTP call -- additive, not a new required
         contract, matching ADR 0064's own `:on-call` rationale (no
         capability kit in this repo mandates quota/audit wiring at the
         transport-construction layer today)."
     ([] (production-transport {}))
     ([{:keys [allowed-origins max-redirects connect-timeout-ms on-call]
        :or {max-redirects default-max-redirects
             connect-timeout-ms default-connect-timeout-ms
             on-call (fn [_])}}]
      (when-not (and (set? allowed-origins) (seq allowed-origins) (every? string? allowed-origins))
        (throw (ex-info "http-transport requires a non-empty :allowed-origins set (the same one given to http/provider)"
                        {:phase :http-transport})))
      (doseq [origin allowed-origins]
        (when-not (= origin (canonical-origin origin))
          (throw (ex-info "http-transport :allowed-origins entries must already be canonical https origins"
                          {:phase :http-transport :origin origin}))))
      (when-not (and (integer? max-redirects) (<= 0 max-redirects 20))
        (throw (ex-info "http-transport :max-redirects must be a small bounded integer in [0, 20]"
                        {:phase :http-transport :max-redirects max-redirects})))
      (let [http-client (-> (HttpClient/newBuilder)
                            ;; Pin HTTP/1.1 explicitly for the same reason as
                            ;; ADR 0064's LLM transport: a plain HTTP/1.1-only
                            ;; server (including this namespace's own
                            ;; `com.sun.net.httpserver` test fakes) cannot
                            ;; negotiate the JDK's default HTTP/2 attempt,
                            ;; surfacing as an opaque IOException rather than
                            ;; a clean protocol error. Real HTTPS endpoints
                            ;; ALPN-negotiate fine either way.
                            (.version HttpClient$Version/HTTP_1_1)
                            ;; NEVER let the JDK auto-follow redirects -- this
                            ;; namespace's own `follow-and-collect!` loop is
                            ;; the only thing allowed to do that, and only
                            ;; within `allowed-origins`. See ns docstring
                            ;; point 1 and docs/adr/0066.
                            (.followRedirects HttpClient$Redirect/NEVER)
                            (.connectTimeout (Duration/ofMillis (long connect-timeout-ms)))
                            (.build))
            allowed-origins-set (set allowed-origins)]
        (fn [{:keys [url headers body timeout-ms]}]
          (let [started (System/currentTimeMillis)
                safe-audit! (fn [event] (try (on-call event) (catch Exception _ nil)))
                result (follow-and-collect!
                        {:http-client http-client
                         :allowed-origins allowed-origins-set
                         :max-redirects max-redirects}
                        url headers body timeout-ms)]
            (safe-audit! {:url url
                          :status (:status result)
                          :error? (boolean (:error result))
                          :latency-ms (- (System/currentTimeMillis) started)})
            result))))))

(def default-get-stream-timeout-ms
  "Per-hop timeout for get-stream (request schema has no timeout field)."
  30000)

#?(:clj
   (defn production-get-stream-transport
     "Synchronous production transport for
     `(provider.http/get-stream-provider {:transport ... :allowed-origins ...})`.

     Input (after `http.cljc` get-stream allow-list + header validation):
     `{:operation :get-stream :url <string> :headers {keyword string}}`.

     Output on success: `{:bytes <byte-array>}` (ready-task shape for
     `as-bytes-task!`). First-hop destination refusal throws
     (redacted by `invoke-get-stream-transport`); network/IO exceptions
     propagate similarly. Same allow-list / redirect / destination-IP
     defenses as `production-transport` (ADR 0066 + ADR 0128)."
     ([] (production-get-stream-transport {}))
     ([{:keys [allowed-origins max-redirects connect-timeout-ms
               timeout-ms on-call]
        :or {max-redirects default-max-redirects
             connect-timeout-ms default-connect-timeout-ms
             timeout-ms default-get-stream-timeout-ms
             on-call (fn [_])}}]
      (when-not (and (set? allowed-origins) (seq allowed-origins) (every? string? allowed-origins))
        (throw (ex-info "http-transport get-stream requires a non-empty :allowed-origins set"
                        {:phase :http-transport})))
      (doseq [origin allowed-origins]
        (when-not (= origin (canonical-origin origin))
          (throw (ex-info "http-transport :allowed-origins entries must already be canonical https origins"
                          {:phase :http-transport :origin origin}))))
      (when-not (and (integer? max-redirects) (<= 0 max-redirects 20))
        (throw (ex-info "http-transport :max-redirects must be a small bounded integer in [0, 20]"
                        {:phase :http-transport :max-redirects max-redirects})))
      (when-not (and (integer? timeout-ms) (pos? timeout-ms))
        (throw (ex-info "http-transport get-stream :timeout-ms must be a positive integer"
                        {:phase :http-transport :timeout-ms timeout-ms})))
      (let [http-client (-> (HttpClient/newBuilder)
                            (.version HttpClient$Version/HTTP_1_1)
                            (.followRedirects HttpClient$Redirect/NEVER)
                            (.connectTimeout (Duration/ofMillis (long connect-timeout-ms)))
                            (.build))
            allowed-origins-set (set allowed-origins)
            hop-timeout (long timeout-ms)]
        (fn [{:keys [operation url headers]}]
          (when-not (or (nil? operation) (= :get-stream operation))
            (throw (ex-info "production-get-stream-transport only accepts :get-stream"
                            {:phase :http-transport :operation operation})))
          (let [started (System/currentTimeMillis)
                safe-audit! (fn [event] (try (on-call event) (catch Exception _ nil)))
                result (follow-and-collect-get!
                        {:http-client http-client
                         :allowed-origins allowed-origins-set
                         :max-redirects max-redirects}
                        url (or headers {}) hop-timeout)]
            (safe-audit! {:url url
                          :operation :get-stream
                          :error? (boolean (:error result))
                          :bytes (when (:bytes result)
                                   (alength ^bytes (:bytes result)))
                          :latency-ms (- (System/currentTimeMillis) started)})
            (if (:error result)
              (throw (ex-info "http get-stream destination blocked"
                              {:phase :http-transport
                               :error (:error result)}))
              result)))))))

#?(:cljs
   (def ^:private hop-script
     "Node one-shot POST (no redirect follow). Reads JSON from stdin, writes JSON to stdout.
     Fields: url, headers (object), body (string), timeoutMs (number)."
     (str
      "const https=require('https');const http=require('http');const {URL}=require('url');\n"
      "const MAX_BODY=65536;const MAX_HEADERS=32;const RESTRICTED=new Set(["
      "'connection','content-length','expect','host','upgrade']);\n"
      "let raw='';process.stdin.setEncoding('utf8');"
      "process.stdin.on('data',c=>raw+=c);process.stdin.on('end',()=>{\n"
      "  const req=JSON.parse(raw);\n"
      "  const u=new URL(req.url);\n"
      "  const lib=u.protocol==='https:'?https:http;\n"
      "  const headers={};\n"
      "  for (const [k,v] of Object.entries(req.headers||{})) {\n"
      "    const lk=String(k).toLowerCase();\n"
      "    if (!RESTRICTED.has(lk)) headers[lk]=String(v);\n"
      "  }\n"
      "  const body=Buffer.from(String(req.body||''),'utf8');\n"
      "  headers['content-length']=String(body.length);\n"
      "  const opts={method:'POST',hostname:u.hostname,port:u.port||(u.protocol==='https:'?443:80),"
      "path:u.pathname+u.search,headers,timeout:Number(req.timeoutMs)||30000};\n"
      "  const r=lib.request(opts,res=>{\n"
      "    const chunks=[];let n=0;\n"
      "    res.on('data',c=>{if(n<MAX_BODY){const take=c.slice(0,MAX_BODY-n);chunks.push(take);n+=take.length;}});\n"
      "    res.on('end',()=>{\n"
      "      const outHeaders={};let count=0;\n"
      "      for (const [k,v] of Object.entries(res.headers||{})) {\n"
      "        if(count>=MAX_HEADERS) break;\n"
      "        const name=String(k).toLowerCase();\n"
      "        if(name.length>512) continue;\n"
      "        const val=Array.isArray(v)?v[0]:v;\n"
      "        if(val==null) continue;\n"
      "        let s=String(val);if(Buffer.byteLength(s,'utf8')>65536) s=s.slice(0,65536);\n"
      "        outHeaders[name]=s;count++;\n"
      "      }\n"
      "      const body=Buffer.concat(chunks).toString('utf8');\n"
      "      process.stdout.write(JSON.stringify({status:res.statusCode,headers:outHeaders,body,"
      "location:res.headers.location||null}));process.exit(0);\n"
      "    });\n"
      "  });\n"
      "  r.on('timeout',()=>{r.destroy();process.stdout.write(JSON.stringify("
      "{error:{code:'http/transport',message:'hop timeout',retryable:true}}));process.exit(0);});\n"
      "  r.on('error',e=>{process.stdout.write(JSON.stringify("
      "{error:{code:'http/transport',message:String(e&&e.message||e),retryable:true}}));process.exit(0);});\n"
      "  r.write(body);r.end();\n"
      "});\n")))

#?(:cljs
   (def ^:private dns-script
     "Resolve host; print JSON {addresses:[...]} or {error:true}."
     (str
      "const dns=require('dns');\n"
      "const host=process.argv[1];\n"
      "dns.lookup(host,{all:true},(err,addrs)=>{\n"
      "  if(err){process.stdout.write(JSON.stringify({error:true}));process.exit(0);return;}\n"
      "  process.stdout.write(JSON.stringify({addresses:(addrs||[]).map(a=>a.address)}));process.exit(0);\n"
      "});\n")))

#?(:cljs
   (def ^:private hop-get-script
     "Node one-shot GET (no redirect follow). Returns bodyBase64 + status + location."
     (str
      "const https=require('https');const http=require('http');const {URL}=require('url');\n"
      "const MAX_BODY=65536;const RESTRICTED=new Set(["
      "'connection','content-length','expect','host','upgrade']);\n"
      "let raw='';process.stdin.setEncoding('utf8');"
      "process.stdin.on('data',c=>raw+=c);process.stdin.on('end',()=>{\n"
      "  const req=JSON.parse(raw);\n"
      "  const u=new URL(req.url);\n"
      "  const lib=u.protocol==='https:'?https:http;\n"
      "  const headers={};\n"
      "  for (const [k,v] of Object.entries(req.headers||{})) {\n"
      "    const lk=String(k).toLowerCase();\n"
      "    if (!RESTRICTED.has(lk)) headers[lk]=String(v);\n"
      "  }\n"
      "  const opts={method:'GET',hostname:u.hostname,port:u.port||(u.protocol==='https:'?443:80),"
      "path:u.pathname+u.search,headers,timeout:Number(req.timeoutMs)||30000};\n"
      "  const r=lib.request(opts,res=>{\n"
      "    const chunks=[];let n=0;\n"
      "    res.on('data',c=>{if(n<MAX_BODY){const take=c.slice(0,MAX_BODY-n);chunks.push(take);n+=take.length;}});\n"
      "    res.on('end',()=>{\n"
      "      const body=Buffer.concat(chunks);\n"
      "      process.stdout.write(JSON.stringify({status:res.statusCode,"
      "bodyBase64:body.toString('base64'),"
      "location:res.headers.location||null}));process.exit(0);\n"
      "    });\n"
      "  });\n"
      "  r.on('timeout',()=>{r.destroy();process.stdout.write(JSON.stringify("
      "{error:{code:'http/transport',message:'hop timeout',retryable:true}}));process.exit(0);});\n"
      "  r.on('error',e=>{process.stdout.write(JSON.stringify("
      "{error:{code:'http/transport',message:String(e&&e.message||e),retryable:true}}));process.exit(0);});\n"
      "  r.end();\n"
      "});\n")))

#?(:cljs
   (defn- private-ip-literal?
     "Pure check for IPv4/IPv6 string literals (no DNS)."
     [host]
     (when (string? host)
       (let [h (if (and (string/starts-with? host "[") (string/ends-with? host "]"))
                 (subs host 1 (dec (count host)))
                 host)]
         (or (= h "0.0.0.0")
             (= h "::")
             (= h "::1")
             (boolean (re-matches #"127\.\d+\.\d+\.\d+" h))
             (boolean (re-matches #"10\.\d+\.\d+\.\d+" h))
             (boolean (re-matches #"192\.168\.\d+\.\d+" h))
             (boolean (re-matches #"169\.254\.\d+\.\d+" h))
             (boolean (re-matches #"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+" h))
             (boolean (re-matches #"(?i)fe80:.*" h))
             (boolean (re-matches #"(?i)f[cd][0-9a-f]{2}:.*" h))
             (boolean (re-matches #"22[4-9]\.\d+\.\d+\.\d+" h))
             (boolean (re-matches #"23\d\.\d+\.\d+\.\d+" h)))))))

#?(:cljs
   (defn- dns-addresses
     [host]
     (let [child (js/require "child_process")
           result (.spawnSync child js/process.execPath
                              #js ["-e" dns-script host]
                              #js {:encoding "utf8" :timeout 5000})]
       (if (or (.-error result) (not (zero? (or (.-status result) 1))))
         []
         (try
           (let [parsed (js->clj (js/JSON.parse (.-stdout result)) :keywordize-keys true)]
             (if (:error parsed) [] (vec (:addresses parsed))))
           (catch :default _ []))))))

#?(:cljs
   (defn destination-blocked?
     "Best-effort private/loopback/link-local/multicast destination block.
     IP literals checked purely; hostnames resolved via child `dns.lookup`.
     DNS failure => not blocked (connect error surfaces on the hop)."
     [host]
     (if (private-ip-literal? host)
       true
       (boolean (some private-ip-literal? (dns-addresses host))))))

#?(:cljs
   (defn- redirect-target
     "Resolve location against base-url; return absolute URL string or nil."
     [base-url location]
     (try
       (let [resolved (str (js/URL. location base-url))]
         (when (and (<= (value/utf8-byte-count! resolved) http/max-url-bytes)
                    (canonical-origin resolved))
           resolved))
       (catch :default _ nil))))

#?(:cljs
   (defn- connect-refusal-reason
     [url allowed-origins]
     (let [origin (canonical-origin url)]
       (cond
         (or (nil? origin) (not (contains? allowed-origins origin))) :not-in-allow-list
         (destination-blocked? (.-hostname (js/URL. url))) :destination-blocked
         :else nil))))

#?(:cljs
   (defn- refusal-error [reason url]
     {:error {:code :http/destination-blocked
              :message (case reason
                         :destination-blocked
                         (str "resolved address for " (.-hostname (js/URL. url))
                              " is not an allowed destination"
                              " (loopback/link-local/private/multicast)")
                         :not-in-allow-list
                         (str "destination is outside the allowed-origins set: " url))
              :retryable false}}))

#?(:cljs
   (defn- send-hop
     "One bounded synchronous POST via spawnSync node; no redirect follow."
     [url headers body timeout-ms]
     (let [child (js/require "child_process")
           payload (js/JSON.stringify
                    (clj->js {:url url
                              :headers (into {} (map (fn [[k v]] [(name k) v]) headers))
                              :body body
                              :timeoutMs timeout-ms}))
           ;; wall-clock bound: hop timeout + connect slack
           wall-ms (+ (long timeout-ms) 5000)
           result (.spawnSync child js/process.execPath
                              #js ["-e" hop-script]
                              #js {:input payload :encoding "utf8" :timeout wall-ms})]
       (cond
         (.-error result)
         {:error {:code :http/transport :message "hop spawn failed" :retryable true}}
         (not (zero? (or (.-status result) 1)))
         (try
           (let [parsed (js->clj (js/JSON.parse (or (.-stdout result) "{}")) :keywordize-keys true)]
             (if (:error parsed) parsed
                 {:error {:code :http/transport :message "hop failed" :retryable true}}))
           (catch :default _
             {:error {:code :http/transport :message "hop failed" :retryable true}}))
         :else
         (try
           (let [parsed (js->clj (js/JSON.parse (.-stdout result)) :keywordize-keys true)]
             (if (:error parsed)
               parsed
               (let [hdrs (into {}
                                (map (fn [[k v]]
                                       [(keyword (string/lower (name k)))
                                        (truncate-to-byte-limit (str v) value/string-value-byte-limit)])
                                     (:headers parsed)))
                     body* (truncate-to-byte-limit (str (:body parsed)) value/string-value-byte-limit)]
                 {:status (:status parsed)
                  :headers hdrs
                  :body body*
                  :location (:location parsed)})))
           (catch :default e
             {:error {:code :http/transport
                      :message (str "hop decode failed: " (.-message e))
                      :retryable false}}))))))

#?(:cljs
   (defn- base64->bytes
     "Decode base64 string to Uint8Array (host :bytes)."
     [b64]
     (let [buf (.from js/Buffer (str b64) "base64")]
       (js/Uint8Array. buf))))

#?(:cljs
   (defn- send-hop-get
     "One bounded synchronous GET via spawnSync node; returns {:bytes ...}."
     [url headers timeout-ms]
     (let [child (js/require "child_process")
           payload (js/JSON.stringify
                    (clj->js {:url url
                              :headers (into {} (map (fn [[k v]] [(name k) v]) headers))
                              :timeoutMs timeout-ms}))
           wall-ms (+ (long timeout-ms) 5000)
           result (.spawnSync child js/process.execPath
                              #js ["-e" hop-get-script]
                              #js {:input payload :encoding "utf8" :timeout wall-ms})]
       (cond
         (.-error result)
         {:error {:code :http/transport :message "hop spawn failed" :retryable true}}
         (not (zero? (or (.-status result) 1)))
         (try
           (let [parsed (js->clj (js/JSON.parse (or (.-stdout result) "{}")) :keywordize-keys true)]
             (if (:error parsed) parsed
                 {:error {:code :http/transport :message "hop failed" :retryable true}}))
           (catch :default _
             {:error {:code :http/transport :message "hop failed" :retryable true}}))
         :else
         (try
           (let [parsed (js->clj (js/JSON.parse (.-stdout result)) :keywordize-keys true)]
             (if (:error parsed)
               parsed
               {:status (:status parsed)
                :bytes (base64->bytes (or (:bodyBase64 parsed) ""))
                :location (:location parsed)}))
           (catch :default e
             {:error {:code :http/transport
                      :message (str "hop decode failed: " (.-message e))
                      :retryable false}}))))))

#?(:cljs
   (defn- follow-and-collect!
     "Redirect loop matching the :clj asymmetry (first-hop refuse vs
     subsequent-hop decline-to-follow)."
     [{:keys [allowed-origins max-redirects]} initial-url headers body timeout-ms]
     (if-let [reason (connect-refusal-reason initial-url allowed-origins)]
       (refusal-error reason initial-url)
       (loop [current-url initial-url
              redirects-left max-redirects]
         (let [resp (send-hop current-url headers body timeout-ms)]
           (if (:error resp)
             resp
             (let [status (:status resp)
                   location (:location resp)
                   candidate (when (and (<= 300 status 399) location (pos? redirects-left))
                               (redirect-target current-url location))]
               (if (and candidate (nil? (connect-refusal-reason candidate allowed-origins)))
                 (recur candidate (dec redirects-left))
                 (dissoc resp :location)))))))))

#?(:cljs
   (defn- follow-and-collect-get!
     "GET redirect loop for get-stream (ADR 0128); final result is {:bytes ...}."
     [{:keys [allowed-origins max-redirects]} initial-url headers timeout-ms]
     (if-let [reason (connect-refusal-reason initial-url allowed-origins)]
       (refusal-error reason initial-url)
       (loop [current-url initial-url
              redirects-left max-redirects]
         (let [resp (send-hop-get current-url headers timeout-ms)]
           (if (:error resp)
             resp
             (let [status (:status resp)
                   location (:location resp)
                   candidate (when (and (<= 300 status 399) location (pos? redirects-left))
                               (redirect-target current-url location))]
               (if (and candidate (nil? (connect-refusal-reason candidate allowed-origins)))
                 (recur candidate (dec redirects-left))
                 (select-keys resp [:bytes])))))))))

#?(:cljs
   (defn production-transport
     "Build a synchronous transport fn for nbb/cljs Node hosts.

     Uses `child_process.spawnSync` + a one-shot Node hop script so the
     reference provider's `(fn [request] -> reply)` contract stays
     synchronous. Redirect loop, allow-list, and destination-IP block match
     the `:clj` transport's semantics (ADR 0066 / ADR 0117).

     Options: same as `:clj` — `:allowed-origins` (required),
     `:max-redirects`, `:on-call`. `:connect-timeout-ms` is accepted for
     API parity but hop timeout is the guest `timeout-ms` (Node request
     timeout); connect-level separation is a remaining gap on cljs."
     ([] (production-transport {}))
     ([{:keys [allowed-origins max-redirects connect-timeout-ms on-call]
        :or {max-redirects default-max-redirects
             connect-timeout-ms default-connect-timeout-ms
             on-call (fn [_])}}]
      (when-not (and (set? allowed-origins) (seq allowed-origins) (every? string? allowed-origins))
        (throw (ex-info "http-transport requires a non-empty :allowed-origins set (the same one given to http/provider)"
                        {:phase :http-transport})))
      (doseq [origin allowed-origins]
        (when-not (= origin (canonical-origin origin))
          (throw (ex-info "http-transport :allowed-origins entries must already be canonical https origins"
                          {:phase :http-transport :origin origin}))))
      (when-not (and (integer? max-redirects) (<= 0 max-redirects 20))
        (throw (ex-info "http-transport :max-redirects must be a small bounded integer in [0, 20]"
                        {:phase :http-transport :max-redirects max-redirects})))
      (let [allowed-origins-set (set allowed-origins)]
        (fn [{:keys [url headers body timeout-ms]}]
          (let [started (js/Date.now)
                safe-audit! (fn [event] (try (on-call event) (catch :default _ nil)))
                result (follow-and-collect!
                        {:allowed-origins allowed-origins-set
                         :max-redirects max-redirects}
                        url headers body timeout-ms)]
            (safe-audit! {:url url
                          :status (:status result)
                          :error? (boolean (:error result))
                          :latency-ms (- (js/Date.now) started)})
            result))))))

#?(:cljs
   (defn production-get-stream-transport
     "nbb/cljs production transport for `:http/get-stream` (ADR 0128).
     Same spawnSync hop pattern as `production-transport`, method GET,
     body returned as host `:bytes` (Uint8Array via base64 hop payload)."
     ([] (production-get-stream-transport {}))
     ([{:keys [allowed-origins max-redirects connect-timeout-ms
               timeout-ms on-call]
        :or {max-redirects default-max-redirects
             connect-timeout-ms default-connect-timeout-ms
             timeout-ms default-get-stream-timeout-ms
             on-call (fn [_])}}]
      (when-not (and (set? allowed-origins) (seq allowed-origins) (every? string? allowed-origins))
        (throw (ex-info "http-transport get-stream requires a non-empty :allowed-origins set"
                        {:phase :http-transport})))
      (doseq [origin allowed-origins]
        (when-not (= origin (canonical-origin origin))
          (throw (ex-info "http-transport :allowed-origins entries must already be canonical https origins"
                          {:phase :http-transport :origin origin}))))
      (when-not (and (integer? max-redirects) (<= 0 max-redirects 20))
        (throw (ex-info "http-transport :max-redirects must be a small bounded integer in [0, 20]"
                        {:phase :http-transport :max-redirects max-redirects})))
      (when-not (and (integer? timeout-ms) (pos? timeout-ms))
        (throw (ex-info "http-transport get-stream :timeout-ms must be a positive integer"
                        {:phase :http-transport :timeout-ms timeout-ms})))
      (let [allowed-origins-set (set allowed-origins)
            hop-timeout (long timeout-ms)]
        (fn [{:keys [operation url headers]}]
          (when-not (or (nil? operation) (= :get-stream operation))
            (throw (ex-info "production-get-stream-transport only accepts :get-stream"
                            {:phase :http-transport :operation operation})))
          (let [started (js/Date.now)
                safe-audit! (fn [event] (try (on-call event) (catch :default _ nil)))
                result (follow-and-collect-get!
                        {:allowed-origins allowed-origins-set
                         :max-redirects max-redirects}
                        url (or headers {}) hop-timeout)]
            (safe-audit! {:url url
                          :operation :get-stream
                          :error? (boolean (:error result))
                          :latency-ms (- (js/Date.now) started)})
            (if (:error result)
              (throw (ex-info "http get-stream destination blocked"
                              {:phase :http-transport
                               :error (:error result)}))
              result)))))))
