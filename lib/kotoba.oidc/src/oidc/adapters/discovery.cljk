(ns oidc.adapters.discovery
  (:require [kotoba.lang.edn :as edn])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers]))

(defn- get-json! [client url decode-json headers]
  (let [builder (HttpRequest/newBuilder (URI/create url))]
    (doseq [[k v] headers]
      (.header builder k v))
    (let [resp (.send client (.build (.GET builder)) (HttpResponse$BodyHandlers/ofString))
          status (.statusCode resp)
          body (.body resp)]
      (if (<= 200 status 299)
        (decode-json body)
        {:error :http/status
         :status status
         :body body}))))

(defn discovery-url [issuer]
  (str issuer "/.well-known/openid-configuration"))

(defn- now-ms [opts]
  (if-let [f (:now-ms opts)] (f) (System/currentTimeMillis)))

(defn- fresh? [entry now ttl-ms]
  (and entry
       (or (nil? ttl-ms)
           (< (- now (:fetched-at-ms entry)) ttl-ms))))

(defn- fetch-with-cache! [cache path key fetch opts]
  (let [now (now-ms opts)
        ttl-ms (:ttl-ms opts)
        refresh? (:refresh? opts)
        entry (get-in @cache [path key])]
    (if (and (not refresh?) (fresh? entry now ttl-ms))
      (:value entry)
      (let [value (fetch)]
        (if (:error value)
          (if (and entry (:allow-stale-on-error? opts))
            (assoc (:value entry)
                   :stale? true
                   :refresh-error value)
            value)
          (do
            (swap! cache assoc-in [path key] {:value value :fetched-at-ms now})
            value))))))

(defn discovery-client
  ([] (discovery-client {}))
  ([opts]
   (let [client (or (:client opts) (HttpClient/newHttpClient))
         decode-json (or (:decode-json opts) edn/read-string)
         cache (atom {})]
     {:fetch-discovery!
      (fn
        ([issuer]
         (fetch-with-cache! cache
                            :discovery
                            issuer
                            #(get-json! client (discovery-url issuer) decode-json (:headers opts))
                            opts))
        ([issuer call-opts]
         (let [opts (merge opts call-opts)]
           (fetch-with-cache! cache
                              :discovery
                              issuer
                              #(get-json! client (discovery-url issuer) decode-json (:headers opts))
                              opts))))
      :fetch-jwks!
      (fn
        ([jwks-uri]
         (fetch-with-cache! cache
                            :jwks
                            jwks-uri
                            #(get-json! client jwks-uri decode-json (:headers opts))
                            opts))
        ([jwks-uri call-opts]
         (let [opts (merge opts call-opts)]
           (fetch-with-cache! cache
                              :jwks
                              jwks-uri
                              #(get-json! client jwks-uri decode-json (:headers opts))
                              opts))))
      :cache cache})))

(defn resolve-config!
  ([client issuer] (resolve-config! client issuer {}))
  ([client issuer opts]
   (let [doc ((:fetch-discovery! client) issuer opts)
         jwks-uri (:jwks_uri doc)
         jwks (when jwks-uri ((:fetch-jwks! client) jwks-uri opts))]
     {:issuer issuer
      :authorization-endpoint (:authorization_endpoint doc)
      :token-endpoint (:token_endpoint doc)
      :userinfo-endpoint (:userinfo_endpoint doc)
      :jwks-uri jwks-uri
      :jwks jwks
      :stale? (or (:stale? doc) (:stale? jwks))
      :refresh-error (or (:refresh-error doc) (:refresh-error jwks))})))
