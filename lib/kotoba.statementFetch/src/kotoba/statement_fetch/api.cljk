(ns kotoba.statement-fetch.api
  "Approved, read-only provider fetches. No write method can be constructed."
  (:require [cljs.reader :as reader]
            [kotoba.statement-fetch.connector :as connector]
            ["node:crypto" :as crypto]
            ["node:fs" :as fs]))

(defn hmac-sign [secret timestamp method path body]
  (-> (.createHmac crypto "sha256" secret)
      (.update (str timestamp method path body))
      (.digest "hex")))

(defn- env! [name']
  (let [value (aget js/process.env name')]
    (when-not (seq value)
      (throw (ex-info (str "Missing required environment variable " name')
                      {:env name'})))
    value))

(defn- request-headers [provider path timestamp token-file]
  (case (:auth/kind provider)
    :hmac-sha256
    (let [key (env! (:auth/api-key-env provider))
          secret (env! (:auth/api-secret-env provider))]
      {"ACCESS-KEY" key
       "ACCESS-TIMESTAMP" timestamp
       "ACCESS-SIGN" (hmac-sign secret timestamp "GET" path "")})

    :oauth2
    (let [token (js->clj
                 (js/JSON.parse (fs/readFileSync token-file "utf8"))
                 :keywordize-keys true)]
      {"Authorization" (str "Bearer " (:access_token token))})

    (throw (ex-info "Provider auth is not an API fetch mechanism" {}))))

(defn fetch-readonly!
  [provider {:keys [path out token-file approved? timestamp]}]
  (when-not approved?
    (throw (ex-info "API fetch requires explicit --approve true" {})))
  (when-not (connector/allowed-request? provider "GET" path)
    (throw (ex-info "Path is not in provider read allowlist" {:path path})))
  (when-not (seq out)
    (throw (ex-info "API fetch requires --out" {})))
  (let [timestamp (or timestamp (str (js/Date.now)))
        headers (request-headers provider path timestamp token-file)]
    (-> (js/fetch (str (:api/base-url provider) path)
                  #js {:method "GET" :headers (clj->js headers)})
        (.then (fn [response]
                 (if (.-ok response)
                   (.json response)
                   (throw (ex-info "Provider API rejected read"
                                   {:status (.-status response)})))))
        (.then
         (fn [payload]
           (let [snapshot {:observed-at (.toISOString (js/Date.))
                           :provider/id (:provider/id provider)
                           :api/path path
                           :payload (js->clj payload :keywordize-keys true)}]
             (fs/writeFileSync out (pr-str snapshot)
                               #js {:encoding "utf8" :mode 384})
             (fs/chmodSync out 384)
             {:api/status :stored :api/output out}))))))
