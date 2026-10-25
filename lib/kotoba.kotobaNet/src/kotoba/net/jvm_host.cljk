(ns kotoba.net.jvm-host
  "JVM host transport for kotoba.net — the ONE place that touches
  java.net.http. Capability-shaped like everything else in kotoba-net:
  `http-transport` returns an injected `transport!` fn
  ({:url :method :headers :body} -> {:status :body :headers}),
  so application code consumes it through `kotoba.net/http-get` and
  `http-post` and never sees java.* types.

  .clj deliberately: HTTP over sockets is a host effect with no ClojureScript
  meaning; the Node/browser counterpart lives with its own host."
  (:require [kotoba.lang.text :as str])
  (:import (java.net URI)
           (java.net.http HttpClient HttpClient$Redirect HttpRequest HttpRequest$BodyPublishers
                          HttpResponse$BodyHandlers)
           (java.time Duration)))

(defn http-transport
  "Build a blocking JVM HTTP transport fn.

  Opts:
    :timeout-seconds — connect + request timeout (default 120)
    :as-bytes        — when true, response body is returned as a byte array
                       instead of a string (for binary artifacts)
    :body-bytes      — when present (byte array), the request body is sent as
                       raw bytes instead of the :body string
    :follow-redirects — when true, HTTP redirects are followed automatically

  Returns `transport!` of shape
    ({:url string :method :get|:post|:put|:patch|:delete
     :headers map :body string} -> {:status int :body string-or-bytes})
  Unsupported methods throw (fail-closed, never a silent default)."
  ([] (http-transport {}))
  ([{:keys [timeout-seconds as-bytes follow-redirects] :or {timeout-seconds 120}}]
   (let [client (-> (HttpClient/newBuilder)
                    (.connectTimeout (Duration/ofSeconds timeout-seconds))
                    (.followRedirects (if follow-redirects
                                        HttpClient$Redirect/NORMAL
                                        HttpClient$Redirect/NEVER))
                    (.build))]
     (fn [{:keys [url method headers body body-bytes]}]
       (let [builder (-> (HttpRequest/newBuilder (URI/create url))
                         (.timeout (Duration/ofSeconds timeout-seconds)))
             builder (reduce-kv (fn [b k v] (.header b (name k) (str v)))
                                builder (or headers {}))
             request (case method
                       :get (-> builder .GET .build)
                       :post (-> builder
                                 (.POST (if body-bytes
                                          (HttpRequest$BodyPublishers/ofByteArray body-bytes)
                                          (HttpRequest$BodyPublishers/ofString (or body ""))))
                                 (.build))
                       :put (-> builder
                                (.PUT (if body-bytes
                                        (HttpRequest$BodyPublishers/ofByteArray body-bytes)
                                        (HttpRequest$BodyPublishers/ofString (or body ""))))
                                (.build))
                       :patch (-> builder
                                  (.method "PATCH"
                                           (if body-bytes
                                             (HttpRequest$BodyPublishers/ofByteArray body-bytes)
                                             (HttpRequest$BodyPublishers/ofString (or body ""))))
                                  (.build))
                       :delete (-> builder .DELETE .build)
                       ;; fail-closed: an unknown method is an error, not a GET
                       (throw (ex-info "unsupported-http-method" {:method method})))]
         (let [handler (if as-bytes
                         (HttpResponse$BodyHandlers/ofByteArray)
                         (HttpResponse$BodyHandlers/ofString))
               resp (.send client request handler)]
           {:status (.statusCode resp)
            :body (.body resp)}))))))
