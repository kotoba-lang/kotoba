(ns saml.adapters.metadata
  (:require [kotoba.lang.text :as str])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers]))

(defn- get-text! [client url headers]
  (let [builder (HttpRequest/newBuilder (URI/create url))]
    (doseq [[k v] headers]
      (.header builder k v))
    (let [resp (.send client (.build (.GET builder)) (HttpResponse$BodyHandlers/ofString))
          status (.statusCode resp)
          body (.body resp)]
      (if (<= 200 status 299)
        {:metadata body}
        {:error :http/status
         :status status
         :body body}))))

(defn metadata-client
  ([] (metadata-client {}))
  ([opts]
   (let [client (or (:client opts) (HttpClient/newHttpClient))
         cache (atom {})]
     {:fetch!
      (fn [metadata-url]
        (or (get @cache metadata-url)
            (let [metadata (get-text! client metadata-url (:headers opts))]
              (swap! cache assoc metadata-url metadata)
              metadata)))
      :cache cache})))

(defn trusted-cert-refs [metadata]
  (vec (keep-indexed
        (fn [idx line]
          (when (re-find #"BEGIN CERTIFICATE|X509Certificate" line)
            (str "metadata-cert:" idx)))
        (str/split-lines (:metadata metadata)))))
