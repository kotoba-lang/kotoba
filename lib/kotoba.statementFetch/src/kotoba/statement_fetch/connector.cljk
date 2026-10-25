(ns kotoba.statement-fetch.connector
  "Pure contracts for read-only financial-data connectors.

  Registrations may describe personal, corporate, or trust owners and bank,
  accounting, brokerage, or crypto accounts. They contain environment-variable
  *names*, never credential values."
  (:require [kotoba.lang.text :as str]))

(def owner-kinds #{:personal :corporate :trust})
(def asset-kinds #{:bank :accounting :brokerage :crypto})
(def auth-kinds #{:handoff :oauth2 :api-key :hmac-sha256})
(def forbidden-registration-keys
  #{:password :secret :token :refresh-token :api-key :client-secret
    :account-number :wallet-private-key :seed-phrase})

(defn- url-encode [value]
  #?(:clj (java.net.URLEncoder/encode (str value) "UTF-8")
     :cljs (js/encodeURIComponent (str value))))

(defn registration-errors [registration]
  (cond-> []
    (not (keyword? (:connection/id registration)))
    (conj {:error/kind :missing-connection-id})
    (not (contains? owner-kinds (:owner/kind registration)))
    (conj {:error/kind :invalid-owner-kind})
    (str/blank? (str (:owner/ref registration)))
    (conj {:error/kind :missing-owner-ref})
    (not (contains? asset-kinds (:asset/kind registration)))
    (conj {:error/kind :invalid-asset-kind})
    (not (keyword? (:provider/id registration)))
    (conj {:error/kind :missing-provider-id})
    (some #(contains? registration %) forbidden-registration-keys)
    (conj {:error/kind :credential-value-forbidden})))

(defn validate-registration [registration]
  (let [errors (registration-errors registration)]
    (when (seq errors)
      (throw (ex-info "Invalid financial connection registration"
                      {:errors errors})))
    registration))

(defn provider-errors [provider]
  (let [auth (:auth/kind provider)
        methods (set (:api/allowed-methods provider))]
    (cond-> []
      (not (keyword? (:provider/id provider)))
      (conj {:error/kind :missing-provider-id})
      (not (contains? auth-kinds auth))
      (conj {:error/kind :invalid-auth-kind})
      (not (or (empty? methods) (= #{"GET"} methods)))
      (conj {:error/kind :write-method-forbidden :methods methods})
      (some #(contains? provider %) forbidden-registration-keys)
      (conj {:error/kind :credential-value-forbidden}))))

(defn validate-provider [provider]
  (let [errors (provider-errors provider)]
    (when (seq errors)
      (throw (ex-info "Invalid provider connector" {:errors errors})))
    provider))

(defn authorization-plan [provider registration {:keys [state redirect-uri]}]
  (validate-provider provider)
  (validate-registration registration)
  (when-not (= (:provider/id provider) (:provider/id registration))
    (throw (ex-info "Registration/provider mismatch" {})))
  (case (:auth/kind provider)
    :handoff
    {:auth/status :operator-required
     :auth/kind :handoff
     :auth/url (:auth/authorize-url provider)
     :auth/note "The operator authenticates; the agent never receives credentials."}

    :oauth2
    (let [_ (when (or (str/blank? state) (str/blank? redirect-uri))
              (throw (ex-info "OAuth plan requires state and redirect-uri" {})))
          client-id-env (:auth/client-id-env provider)
          scopes (str/join " " (:auth/scopes provider))
          query [["response_type" "code"]
                 ["client_id" (str "${" client-id-env "}")]
                 ["redirect_uri" redirect-uri]
                 ["scope" scopes]
                 ["state" state]]]
      {:auth/status :operator-required
       :auth/kind :oauth2
       :auth/client-id-env client-id-env
       :auth/client-secret-env (:auth/client-secret-env provider)
       :auth/token-url (:auth/token-url provider)
       :auth/url
       (str (:auth/authorize-url provider) "?"
            (str/join "&" (map (fn [[k v]]
                                  (str k "=" (url-encode v))) query)))
       :auth/note "Open this URL after substituting the local client id. Verify state at callback."})

    :api-key
    {:auth/status :operator-required
     :auth/kind (:auth/kind provider)
     :auth/required-env (vec (remove nil? [(:auth/api-key-env provider)]))
     :auth/note "Create a read-only key. Write permissions must remain disabled."}

    :hmac-sha256
    {:auth/status :operator-required
     :auth/kind (:auth/kind provider)
     :auth/required-env (vec (remove nil?
                                    [(:auth/api-key-env provider)
                                     (:auth/api-secret-env provider)]))
     :auth/note "Create a read-only key. Trading, transfer, and withdrawal permissions must remain disabled."}))

(defn allowed-request? [provider method path]
  (and (contains? (set (:api/allowed-methods provider)) method)
       (some #(= path %) (:api/read-paths provider))))

(defn normalize-snapshot
  "Attach ownership and provenance to already-fetched provider facts.
  Provider adapters remain responsible for exact number parsing."
  [registration {:keys [observed-at balances transactions] :as snapshot}]
  (validate-registration registration)
  (when-not observed-at
    (throw (ex-info "Snapshot requires :observed-at" {})))
  {:finance/connection (:connection/id registration)
   :finance/owner {:kind (:owner/kind registration)
                   :ref (:owner/ref registration)}
   :finance/provider (:provider/id registration)
   :finance/asset-kind (:asset/kind registration)
   :finance/observed-at observed-at
   :finance/balances
   (mapv #(assoc % :owner/ref (:owner/ref registration)
                   :connection/id (:connection/id registration))
         (or balances []))
   :finance/transactions
   (mapv #(assoc % :owner/ref (:owner/ref registration)
                   :connection/id (:connection/id registration))
         (or transactions []))
   :finance/source-hash (:source-hash snapshot)})
