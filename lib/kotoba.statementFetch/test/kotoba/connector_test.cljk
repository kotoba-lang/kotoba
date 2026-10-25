(ns kotoba.connector-test
  (:require [cljs.test :refer [deftest is]]
            [kotoba.statement-fetch.api :as api]
            [kotoba.statement-fetch.connector :as connector]))

(def registration
  {:connection/id :personal/main-bank
   :owner/kind :personal :owner/ref :owner/self
   :asset/kind :bank :provider/id :bank/browser})

(deftest registrations-separate-owner-and-asset-kind
  (is (= registration (connector/validate-registration registration)))
  (is (thrown? js/Error
               (connector/validate-registration
                (assoc registration :account-number "1234567")))))

(deftest providers-are-read-only
  (let [provider {:provider/id :crypto/example
                  :auth/kind :hmac-sha256
                  :auth/api-key-env "EXAMPLE_KEY"
                  :auth/api-secret-env "EXAMPLE_SECRET"
                  :api/allowed-methods ["GET"]
                  :api/read-paths ["/v1/me/getbalance"]}]
    (is (connector/allowed-request? provider "GET" "/v1/me/getbalance"))
    (is (not (connector/allowed-request? provider "POST" "/v1/me/withdraw")))
    (is (thrown? js/Error
                 (connector/validate-provider
                  (assoc provider :api/allowed-methods ["GET" "POST"]))))))

(deftest normalization-preserves-provenance
  (let [result
        (connector/normalize-snapshot
         registration
         {:observed-at "2026-07-26T00:00:00Z"
          :balances [{:asset "JPY" :amount-minor 1000}]
          :transactions [{:external-id "t1" :amount-minor -100}]})]
    (is (= :personal (get-in result [:finance/owner :kind])))
    (is (= :owner/self
           (get-in result [:finance/transactions 0 :owner/ref])))))

(deftest oauth-plans-require-csrf-state
  (let [provider {:provider/id :accounting/example
                  :auth/kind :oauth2
                  :auth/authorize-url "https://example.test/authorize"
                  :auth/token-url "https://example.test/token"
                  :auth/client-id-env "EXAMPLE_ID"
                  :auth/client-secret-env "EXAMPLE_SECRET"
                  :auth/scopes ["read"]
                  :api/allowed-methods ["GET"]
                  :api/read-paths ["/balances"]}
        registration (assoc registration
                            :provider/id :accounting/example
                            :asset/kind :accounting)]
    (is (thrown? js/Error
                 (connector/authorization-plan
                  provider registration {:redirect-uri "http://localhost"})))
    (is (= :operator-required
           (:auth/status
            (connector/authorization-plan
             provider registration
             {:state "random" :redirect-uri "http://127.0.0.1/callback"}))))))

(deftest bitflyer-signing-is-deterministic
  (is (= (api/hmac-sign "secret" "1" "GET" "/v1/me/getbalance" "")
         (api/hmac-sign "secret" "1" "GET" "/v1/me/getbalance" "")))
  (is (not= (api/hmac-sign "secret" "1" "GET" "/a" "")
            (api/hmac-sign "secret" "1" "GET" "/b" ""))))
