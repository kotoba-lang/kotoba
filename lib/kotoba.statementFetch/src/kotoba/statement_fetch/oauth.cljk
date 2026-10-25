(ns kotoba.statement-fetch.oauth
  "OAuth code exchange boundary for local read-only connectors."
  (:require ["node:fs" :as fs]))

(defn- required-env [name']
  (let [value (aget js/process.env name')]
    (when-not (seq value)
      (throw (ex-info (str "Missing required environment variable " name')
                      {:env name'})))
    value))

(defn exchange!
  [provider {:keys [code-env expected-state returned-state redirect-uri
                    token-out approved?]}]
  (when-not approved?
    (throw (ex-info "OAuth exchange requires explicit --approve true" {})))
  (when-not (and (seq expected-state) (= expected-state returned-state))
    (throw (ex-info "OAuth callback state mismatch" {})))
  (when-not (seq token-out)
    (throw (ex-info "OAuth exchange requires --token-out" {})))
  (let [client-id (required-env (:auth/client-id-env provider))
        client-secret (required-env (:auth/client-secret-env provider))
        code (required-env code-env)
        body (js/URLSearchParams.)]
    (.set body "grant_type" "authorization_code")
    (.set body "code" code)
    (.set body "client_id" client-id)
    (.set body "client_secret" client-secret)
    (.set body "redirect_uri" redirect-uri)
    (-> (js/fetch (:auth/token-url provider)
                  #js {:method "POST"
                       :headers #js {"content-type"
                                     "application/x-www-form-urlencoded"}
                       :body body})
        (.then
         (fn [response]
           (if (.-ok response)
             (.json response)
             (-> (.text response)
                 (.then
                  (fn [text]
                    (throw
                     (ex-info "OAuth token endpoint rejected exchange"
                              {:status (.-status response)
                               :body-length (count text)}))))))))
        (.then
         (fn [token]
           ;; Never print or return the token payload. The file is local and
           ;; owner-readable only.
           (fs/writeFileSync token-out (js/JSON.stringify token)
                             #js {:encoding "utf8" :mode 384})
           (fs/chmodSync token-out 384)
           {:auth/status :stored :auth/token-file token-out})))))
