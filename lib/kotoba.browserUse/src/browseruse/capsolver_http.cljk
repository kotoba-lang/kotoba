(ns browseruse.capsolver-http
  "Small JVM JSON transport for browseruse.capsolver."
  (:require [cheshire.core :as json])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpRequest$BodyPublishers
            HttpResponse$BodyHandlers]
           [java.time Duration]))

(defn request!
  "Execute a portable CapSolver request map. The request body and credentials
  are never logged. `:timeout-ms` defaults to 30 seconds."
  [{:keys [url headers body timeout-ms] :or {timeout-ms 30000}}]
  (let [builder (doto (HttpRequest/newBuilder (URI/create url))
                  (.timeout (Duration/ofMillis timeout-ms))
                  (.POST (HttpRequest$BodyPublishers/ofString
                          (json/generate-string body))))
        _ (doseq [[k v] headers] (.header builder k v))
        response (.send (HttpClient/newHttpClient) (.build builder)
                        (HttpResponse$BodyHandlers/ofString))]
    {:status (.statusCode response)
     :body (json/parse-string (.body response) true)}))
