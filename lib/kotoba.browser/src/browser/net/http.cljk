(ns browser.net.http
  "Real host I/O for the `:browser.session/fetch-fn` / `browser.net` injection
   point.

   `browser.net` documents that fetch I/O is injected by the host: it owns
   origin/CORS/cookie/cache *policy* and calls a supplied `fetch-fn` of shape
   `{:url :method :headers :body} -> {:status :headers :body}` to actually
   move bytes. Every fetch-fn in this repo's tests up to now has been a fake
   (`(constantly {:status 200 ...})`). This namespace is the first real
   implementation of that capability: it opens a socket via the JDK's
   `java.net.http.HttpClient` (built in, no new dependency) and translates
   to/from this repo's request/response shape.

   This namespace intentionally does not know about origin, CORS, cookies, or
   caching — that policy stays in `browser.net`. It also does not follow
   HTTP redirects itself: `browser.session/navigate!` already implements
   redirect-following (up to depth 8) by inspecting the response status and
   `location` header and calling fetch-fn again, so the underlying HTTP
   client is configured to never auto-follow redirects.

   A real network failure (connection refused, unknown host, timeout, ...)
   never throws out of the returned fetch-fn: it comes back as a response map
   with `:status 0` and an `:error` keyword, matching the existing
   `browser.net` convention for non-HTTP outcomes (permission-denied and
   CORS-blocked responses already use `:status 0` + `:error`)."
  (:require [kotoba.lang.text :as str]))

(def default-connect-timeout-ms
  "Default TCP connect timeout for the JVM HttpClient."
  10000)

(def default-request-timeout-ms
  "Default end-to-end request timeout (connect + send + receive headers/body)."
  30000)

#?(:clj
   (do

     (defn create-client
       "Build a java.net.http.HttpClient tuned for use as a browser.net
        fetch-fn backend: bounded connect timeout, redirects left to the
        caller (browser.session already implements redirect-following)."
       (^java.net.http.HttpClient []
        (create-client {}))
       (^java.net.http.HttpClient [{:keys [connect-timeout-ms]
                                     :or {connect-timeout-ms default-connect-timeout-ms}}]
        (-> (java.net.http.HttpClient/newBuilder)
            (.connectTimeout (java.time.Duration/ofMillis connect-timeout-ms))
            (.followRedirects java.net.http.HttpClient$Redirect/NEVER)
            ;; Force HTTP/1.1. The JDK client's default (HTTP/2 with an h2c
            ;; upgrade attempt, falling back to 1.1) is unreliable against
            ;; plain HTTP/1.1-only servers -- e.g. the JDK's own
            ;; com.sun.net.httpserver.HttpServer used in this repo's tests --
            ;; intermittently failing with "header parser received no bytes"
            ;; instead of falling back cleanly. Pinning HTTP_1_1 trades away
            ;; HTTP/2 (including over TLS) for correctness; revisit if/when a
            ;; real target needs HTTP/2.
            (.version java.net.http.HttpClient$Version/HTTP_1_1)
            (.build))))

     (defn- header-name-str
       [k]
       (if (keyword? k) (name k) (str k)))

     (defn- header-values
       [v]
       (if (sequential? v) (map str v) [(str v)]))

     (defn- add-request-header!
       "HttpRequest.Builder#header throws for a handful of JDK-restricted
        headers (host, content-length, connection, ...). browser.net never
        sets those, but be defensive rather than let an unexpected header
        blow up an entire navigation with an uncaught exception."
       ^java.net.http.HttpRequest$Builder
       [^java.net.http.HttpRequest$Builder builder header-name value]
       (try
         (.header builder (str header-name) value)
         (catch IllegalArgumentException _ builder)))

     (defn- apply-headers
       ^java.net.http.HttpRequest$Builder
       [^java.net.http.HttpRequest$Builder builder headers]
       (doseq [[k v] headers
               line (header-values v)]
         (add-request-header! builder (header-name-str k) line))
       builder)

     (defn- body-publisher
       [body]
       (if (some? body)
         (java.net.http.HttpRequest$BodyPublishers/ofString (str body))
         (java.net.http.HttpRequest$BodyPublishers/noBody)))

     (defn- ->http-request
       ^java.net.http.HttpRequest
       [{:keys [url method headers body]} {:keys [request-timeout-ms]
                                            :or {request-timeout-ms default-request-timeout-ms}}]
       (-> (java.net.http.HttpRequest/newBuilder (java.net.URI/create (str url)))
           (.timeout (java.time.Duration/ofMillis request-timeout-ms))
           (apply-headers headers)
           (.method (str/upper (name (or method :get))) (body-publisher body))
           (.build)))

     (defn- response-headers
       [^java.net.http.HttpResponse response]
       (into {}
             (map (fn [[k vs]]
                    [k (if (= 1 (count vs)) (first vs) (vec vs))]))
             (.map (.headers response))))

     (defn- ->response
       [^java.net.http.HttpResponse response]
       {:status (.statusCode response)
        :headers (response-headers response)
        :body (.body response)})

     (defn- ex-message*
       "Some exceptions (e.g. ConnectException on a refused connection) have a
        nil .getMessage; fall back to the class name so :error/message is
        always a string."
       [^Throwable e]
       (or (.getMessage e) (.getName (class e))))

     (defn fetch!
       "Perform one real HTTP request and return a browser.net-shaped
        response map: {:status :headers :body}, or on failure
        {:status 0 :error <keyword> :error/message <string>}.

        `client` is a java.net.http.HttpClient (see create-client). `request`
        is {:url :method :headers :body} (method/headers/body optional,
        method defaults to :get). `opts` accepts :request-timeout-ms."
       ([client request]
        (fetch! client request {}))
       ([^java.net.http.HttpClient client request opts]
        (try
          (let [http-request (->http-request request opts)
                response (.send client http-request
                                 (java.net.http.HttpResponse$BodyHandlers/ofString))]
            (->response response))
          (catch java.net.http.HttpTimeoutException e
            {:status 0 :error :net/timeout :error/message (ex-message* e)})
          (catch java.net.UnknownHostException e
            {:status 0 :error :net/unknown-host :error/message (ex-message* e)})
          (catch java.net.ConnectException e
            {:status 0 :error :net/connection-refused :error/message (ex-message* e)})
          (catch java.io.IOException e
            {:status 0 :error :net/io-error :error/message (ex-message* e)})
          (catch InterruptedException e
            (.interrupt (Thread/currentThread))
            {:status 0 :error :net/interrupted :error/message (ex-message* e)})
          (catch IllegalArgumentException e
            {:status 0 :error :net/invalid-request :error/message (ex-message* e)})
          (catch Exception e
            {:status 0 :error :net/fetch-failed :error/message (ex-message* e)}))))

     (defn fetch-fn
       "Return a fetch-fn (the function shape browser.session/new-session and
        browser.core/navigate expect at :fetch-fn / :fetch-fn) backed by a
        real, shared java.net.http.HttpClient.

        Options: :connect-timeout-ms, :request-timeout-ms (see the
        default-*-ms vars above). A fresh client is built once per call to
        `fetch-fn` and reused (connection-pooled) across every request the
        returned function makes."
       ([] (fetch-fn {}))
       ([opts]
        (let [client (create-client opts)]
          (fn real-fetch-fn [request]
            (fetch! client request opts)))))))

#?(:cljs
   (do
     ;; Sketch only, not wired into anything and not covered by tests in this
     ;; change: this repo's fetch-fn contract is synchronous
     ;; (`(fetch-fn request) => response-map`), but js/fetch is inherently
     ;; async (Promise-returning). A real CLJS fetch-fn would need either a
     ;; host-level bridge that can block/park (e.g. a core.async channel
     ;; consumed by an async-aware caller) or a change to the fetch-fn
     ;; contract itself -- both are out of scope here. `fetch-async` below
     ;; shows the request/response translation only; it is left as a
     ;; documented follow-up rather than a second, unverified I/O path.
     (defn- js-headers
       [headers]
       (let [h (js/Headers.)]
         (doseq [[k v] headers]
           (.append h (name k) (str v)))
         h))

     (defn fetch-async
       "Translate a browser.net-shaped request into a js/fetch call and
        return a Promise of a browser.net-shaped response map. Not a
        drop-in fetch-fn (see namespace note above) -- a real caller would
        need to bridge this Promise back into the synchronous contract."
       [{:keys [url method headers body]}]
       (-> (js/fetch url #js {:method (str/upper (name (or method :get)))
                              :headers (js-headers headers)
                              :body (when (some? body) body)
                              :redirect "manual"})
           (.then (fn [resp]
                    (-> (.text resp)
                        (.then (fn [text]
                                 {:status (.-status resp)
                                  :headers (into {}
                                                 (map (fn [[k v]] [k v]))
                                                 (es6-iterator-seq (.entries (.-headers resp))))
                                  :body text})))))
           (.catch (fn [err]
                     {:status 0
                      :error :net/fetch-failed
                      :error/message (str (.-message err))}))))))
