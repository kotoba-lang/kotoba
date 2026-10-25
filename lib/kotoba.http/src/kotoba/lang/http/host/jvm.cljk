(ns kotoba.lang.http.host.jvm
  "JVM host adapter for OUTBOUND HTTP over `java.net.http` — the JDK's own
  client, so this adapter adds no dependency at all.

  ## Why this exists next to `host/babashka`

  Both are client hosts, and they are not redundant. `host/babashka` wraps
  `org.babashka/http-client`, which is bundled under Babashka but is an added
  dependency on a plain JVM (`:babashka-client-host`). `java.net.http` ships
  with the JDK from 11, so a consumer that is already on the JVM gets a
  transport without widening its dependency set — which is what a repository
  whose README says `zero third-party runtime deps` should be able to offer.

  It is the missing corner of this repo's host table, and its absence was
  measured rather than assumed. On 2026-09-07, cloud-itonami-app rewrote 35
  namespaces to route every `java.net.http` call through one shim, requiring
  `kotoba.net.jvm-host`. That namespace was never written -- not in this
  workspace, and (searched 2026-09-09) nowhere on GitHub. The application
  could not load at all for two days: 36 namespaces require the shim, the
  shim required a namespace that did not exist, and the Windows launch smoke
  went red on every run while nothing said why in terms anyone acted on.

  The instinct behind that commit was right. `java.net.http` is a host
  capability, an application should not have its own copy of one, and this
  repository is where HTTP transports live. What was missing was the
  transport, not the intention.

  ## The response shape, and why it is this one

  `{:status int :headers {lowercase-name value} :body string}`.

  Header names are lower-cased and multi-valued headers collapse to their
  FIRST value. That is not a fresh design decision -- it is the contract the
  call sites were written against before the migration, and ACME reads
  `[:headers \"replay-nonce\"]` and `[:headers \"location\"]` positionally.
  Changing the arity here would break a protocol handshake in a way no type
  would catch.

  The lower-casing is belt-and-braces, and measured to be so: `HttpHeaders`
  already returns its keys folded, so removing the `toLowerCase` on 2026-09-09
  left a round-trip test green. It stays because the contract is this
  namespace's to state rather than the JDK's to keep -- but it is checked
  where it can actually be checked, by `normalize-headers` on a map with
  mixed-case keys, and not by a round trip that cannot tell who folded them.

  ## Fail closed on an unknown method

  `method->name` throws rather than defaulting to GET. A transport that
  silently downgrades an unrecognised method turns a write into a read, which
  succeeds, returns 200, and changes nothing -- the failure that looks most
  like success."
  #?(:clj (:require [kotoba.lang.http :as http]))
  #?(:clj (:import [java.net URI]
                   [java.net.http HttpClient HttpClient$Redirect
                    HttpRequest HttpResponse
                    HttpRequest$BodyPublishers HttpResponse$BodyHandlers]
                   [java.time Duration]
                   [java.util.function Function])))

#?(:clj
   (def ^:private methods-with-body
     "POST, PUT and PATCH carry a body; GET, DELETE and HEAD do not. Listed so
      an unknown method cannot fall into either branch by accident."
     #{:post :put :patch}))

#?(:clj
   (defn- method->name [method]
     (let [k (keyword (if (string? method) (.toLowerCase ^String method) (name method)))]
       (case k
         :get "GET" :post "POST" :put "PUT" :patch "PATCH"
         :delete "DELETE" :head "HEAD" :options "OPTIONS"
         (throw (ex-info "kotoba.lang.http.host.jvm: unsupported HTTP method"
                         {:method method}))))))

#?(:clj
   (defn normalize-headers
     "`java.net.http`'s header map -> {lowercase-name first-value}.

      Public and separate from `response->map` so the rule can be tested on an
      input this namespace controls. Through a real request it cannot be: the
      JDK folds the keys before they get here, so a round trip stays green
      whether or not this function folds anything.

      The rule itself moved to `kotoba.lang.http/fold-headers` when host/node
      arrived and needed the same answer. This name stays because it is the one
      this host's tests and its consumers already use."
     [header-map]
     (http/fold-headers header-map)))

#?(:clj
   (defn- response->map [^HttpResponse resp]
     {:status (.statusCode resp)
      :headers (normalize-headers (.map (.headers resp)))
      :body (.body resp)}))

#?(:clj
   (defn- build-client
     "One client construction, shared by the sync and async transports. Two
      copies of `Redirect/NORMAL` is how one of them stops following."
     [connect-timeout-seconds]
     (-> (HttpClient/newBuilder)
         (.connectTimeout (Duration/ofSeconds (long (or connect-timeout-seconds 30))))
         (.followRedirects HttpClient$Redirect/NORMAL)
         (.build))))

#?(:clj
   (defn- build-request
     "One request construction, likewise. The method is resolved through
      `method->name`, so an unsupported method is refused here -- before either
      transport sends anything, and on the caller's own stack rather than inside
      a future it may not be looking at."
     [{:keys [url method headers body body-bytes] :as req} timeout-seconds]
     (when (and (contains? req :body-bytes)
                (or (not (bytes? body-bytes)) (contains? req :body)))
       (throw (ex-info "body-bytes requires a byte array and excludes body" {})))
     (let [secs (long (or (:timeout-seconds req) timeout-seconds 120))
           publisher (if (contains? methods-with-body (keyword (name (or method :get))))
                       (if (contains? req :body-bytes)
                         (HttpRequest$BodyPublishers/ofByteArray body-bytes)
                         (HttpRequest$BodyPublishers/ofString (str (or body ""))))
                       (HttpRequest$BodyPublishers/noBody))
           builder (-> (HttpRequest/newBuilder)
                       (.uri (URI/create url))
                       (.timeout (Duration/ofSeconds secs))
                       (.method (method->name (or method :get)) publisher))]
       (doseq [[k v] headers]
         (.header builder (if (keyword? k) (name k) (str k)) (str v)))
       (.build builder))))

#?(:clj
   (defn- response-handler [req]
     (case (:response-type req)
       (nil :text) (HttpResponse$BodyHandlers/ofString)
       :bytes (HttpResponse$BodyHandlers/ofByteArray)
       (throw (ex-info "Unsupported response-type" {:response-type (:response-type req)})))))

#?(:clj
   (defn http-transport
     "Return a function of a request map, performing it over `java.net.http`.

      req  {:url string
            :method :get|:post|:put|:patch|:delete|:head|:options
            :headers {string-or-keyword value}   optional
            :body string                         optional
            :body-bytes byte-array               optional, excludes :body
            :response-type :text|:bytes}          optional, defaults to text
      ->   {:status int :headers {lowercase-name value} :body string-or-bytes}

      Byte mode preserves every octet without a text/base64 round trip.
      `:timeout-seconds` bounds the request; it is required to be present in
      opts or in the request rather than defaulted here, because a transport
      with no timeout is how one unreachable host stops a whole process, and
      the right bound belongs to the caller who knows what it is calling."
     ([] (http-transport {}))
     ([{:keys [timeout-seconds connect-timeout-seconds]}]
      (let [client (build-client connect-timeout-seconds)]
        (fn [req]
          (response->map
           (.send client (build-request req timeout-seconds)
                  (response-handler req))))))))

#?(:clj
   (defn http-transport-async
     "The same request, returning a `CompletableFuture` of the same response map.

      The synchronous `http-transport` above blocks the calling thread until the
      response arrives. `host/node` cannot block at all -- Node has no
      in-process synchronous HTTP -- so an application that wants ONE shape on
      both runtimes has to be the asynchronous one, and this is the JVM half of
      it.

      `HttpClient.sendAsync` rather than a thread that waits on the sync call:
      wrapping a blocking send in a future is asynchronous to its caller and
      still holds a thread for the whole round trip, which is the cost the shape
      was adopted to avoid.

      A CompletableFuture, and deliberately not a promesa promise: this
      repository ships zero third-party runtime dependencies and that is a
      property worth more than the convenience. promesa treats a
      CompletableFuture and a js/Promise as the same thing, so an application
      that already has it can put both hosts behind one API -- which is the
      layer where a dependency belongs."
     ([] (http-transport-async {}))
     ([{:keys [timeout-seconds connect-timeout-seconds]}]
      (let [client (build-client connect-timeout-seconds)]
        (fn [req]
          (.thenApply
           (.sendAsync client
                       (build-request req timeout-seconds)
                       (response-handler req))
           (reify Function (apply [_ resp] (response->map resp))))))))) 

#?(:clj
   (defn ->http
     "The same transport as an `IHttp`, so it plugs into this repo's own seam
      rather than only into callers that want a bare function."
     ([] (->http {}))
     ([opts]
      (let [send-fn (http-transport opts)]
        (reify http/IHttp
          (send [_ req] (send-fn req)))))))
