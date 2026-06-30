(ns kotoba.wallet-test
  (:require [clojure.test :refer [deftest is run-tests]]
            [kotoba.wallet.actor :as actor]
            [kotoba.wallet.provider :as provider]
            [kotoba.wallet.risk :as risk]
            [kotoba.wallet.runtime :as runtime]
            [kotoba.wallet.store :as store]
            [kotoba.wallet.swap :as swap]
            [kotoba.wallet.tx :as tx]))

(def account
  {:id "acct:main"
   :did "did:key:zAlice"
   :pkh "did:pkh:eip155:1:0xabc0000000000000000000000000000000000000"
   :address "0xabc0000000000000000000000000000000000000"
   :label "Main"
   :custody :custody/passkey
   :created-at 1782560000000})

(def other-account
  {:id "acct:other"
   :did "did:key:zBob"
   :pkh "did:pkh:eip155:1:0xbbb0000000000000000000000000000000000000"
   :address "0xbbb0000000000000000000000000000000000000"
   :label "Other"
   :custody :custody/passkey
   :created-at 1782560000001})

(def network
  {:chain-id 1
   :name "Ethereum Mainnet"
   :namespace "eip155"
   :native-symbol "ETH"
   :rpc-ref "rpc:mainnet"
   :status :network.status/enabled})

(def base-network
  {:chain-id 8453
   :name "Base"
   :namespace "eip155"
   :native-symbol "ETH"
   :rpc-ref "rpc:base"
   :status :network.status/enabled})

(defn ready-state []
  (-> actor/empty-state
      (actor/apply-event [:account/connected account])
      (actor/apply-event [:network/added network])
      (actor/apply-event [:network/selected {:chain-id 1}])
      (actor/apply-event [:policy/granted {:origin "https://app.example"
                                           :accounts ["acct:main"]
                                           :chains [1 8453]
                                           :caps #{:eth/accounts :eth/chain-id :eth/switch-chain
                                                   :eth/add-chain :eth/watch-asset :eth/call
                                                   :eth/estimate-gas :eth/send-tx
                                                   :eth/prepare-transfer :eth/revoke-approval
                                                   :eth/quote-swap :eth/prepare-swap
                                                   :eth/sign-message :eth/sign-typed-data}
                                           :max-slippage-bps 100
                                           :allowed-spenders #{"0xrouter"}
                                           :allow-unlimited-approval? false}])))

(deftest datom-wire-keeps-wallet-secrets-out
  (let [txs (store/account->tx account)]
    (is (some #(= ":wallet.account/address" (:a %)) txs))
    (is (not-any? #(re-find #"private|seed|mnemonic|rpc/url" (str %)) txs))))

(deftest balance-observation-is-state-and-datoms
  (let [balance {:account-id "acct:main"
                 :chain-id 1
                 :asset "native"
                 :block-number 23000000
                 :raw "123450000000000000"
                 :observed-at 1782560000100}
        result (actor/step (ready-state) [:wallet/observe-balance balance])]
    (is (= balance (get-in result [:state :balances ["acct:main" 1 "native"]])))
    (is (some #(= ":wallet.balance/raw" (:a %)) (:datoms result)))))

(deftest allowance-observation-is-state-and-datoms
  (let [allowance {:account-id "acct:main"
                   :chain-id 1
                   :token "0xusdc"
                   :spender "0xrouter"
                   :amount "1000000"
                   :block-number 23000000
                   :observed-at 1782560000150}
        result (actor/step (ready-state) [:wallet/observe-allowance allowance])]
    (is (= "1000000"
           (get-in result [:state :allowances ["acct:main" 1 "0xusdc" "0xrouter"]])))
    (is (some #(= ":wallet.allowance/amount" (:a %)) (:datoms result)))
    (is (some #(= ":wallet.allowance/spender" (:a %)) (:datoms result)))))

(deftest balance-and-allowance-observations-require-auditable-provenance
  (let [missing-balance-fields (try
                                 (actor/step (ready-state)
                                             [:wallet/observe-balance
                                              {:account-id "acct:main"
                                               :chain-id 1
                                               :raw "42"}])
                                 (catch clojure.lang.ExceptionInfo e
                                   (ex-data e)))
        invalid-balance-block (try
                                (actor/step (ready-state)
                                            [:wallet/observe-balance
                                             {:account-id "acct:main"
                                              :chain-id 1
                                              :asset "native"
                                              :block-number 0
                                              :raw "42"
                                              :observed-at 1782560000100}])
                                (catch clojure.lang.ExceptionInfo e
                                  (ex-data e)))
        invalid-balance-raw (try
                              (actor/step (ready-state)
                                          [:wallet/observe-balance
                                           {:account-id "acct:main"
                                            :chain-id 1
                                            :asset "native"
                                            :block-number 23000000
                                            :raw "0x2a"
                                            :observed-at 1782560000100}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        missing-allowance-fields (try
                                   (actor/step (ready-state)
                                               [:wallet/observe-allowance
                                                {:account-id "acct:main"
                                                 :chain-id 1
                                                 :token "0xusdc"
                                                 :amount "1000000"
                                                 :block-number 23000000
                                                 :observed-at 1782560000150}])
                                   (catch clojure.lang.ExceptionInfo e
                                     (ex-data e)))
        invalid-allowance-observed-at (try
                                        (actor/step (ready-state)
                                                    [:wallet/observe-allowance
                                                     {:account-id "acct:main"
                                                      :chain-id 1
                                                      :token "0xusdc"
                                                      :spender "0xrouter"
                                                      :amount "1000000"
                                                      :block-number 23000000
                                                      :observed-at "1782560000150"}])
                                        (catch clojure.lang.ExceptionInfo e
                                          (ex-data e)))
        invalid-allowance-amount (try
                                   (actor/step (ready-state)
                                               [:wallet/observe-allowance
                                                {:account-id "acct:main"
                                                 :chain-id 1
                                                 :token "0xusdc"
                                                 :spender "0xrouter"
                                                 :amount "-1"
                                                 :block-number 23000000
                                                 :observed-at 1782560000150}])
                                   (catch clojure.lang.ExceptionInfo e
                                     (ex-data e)))]
    (is (= :wallet.observation/missing-fields (:kind missing-balance-fields)))
    (is (= [:block-number :observed-at] (:missing missing-balance-fields)))
    (is (= :balance/observed (:observation missing-balance-fields)))
    (is (= :block-number (:field invalid-balance-block)))
    (is (= 0 (:actual invalid-balance-block)))
    (is (= :raw (:field invalid-balance-raw)))
    (is (= "0x2a" (:actual invalid-balance-raw)))
    (is (= :wallet.observation/missing-fields (:kind missing-allowance-fields)))
    (is (= [:spender] (:missing missing-allowance-fields)))
    (is (= :allowance/observed (:observation missing-allowance-fields)))
    (is (= :observed-at (:field invalid-allowance-observed-at)))
    (is (= "1782560000150" (:actual invalid-allowance-observed-at)))
    (is (= :amount (:field invalid-allowance-amount)))
    (is (= "-1" (:actual invalid-allowance-amount)))))

(deftest tx-normalization-and-intent-hash-are-stable
  (let [intent (tx/tx->intent
                "intent:1"
                (tx/normalize-tx 1 {:account-id "acct:main"
                                    :from "0xABC0000000000000000000000000000000000000"
                                    :to "0xDEF0000000000000000000000000000000000000"
                                    :data "AABB"
                                    :value 10
                                    :origin "https://app.example"}))]
    (is (= "0xabc0000000000000000000000000000000000000" (:from intent)))
    (is (= "0xaabb" (:data intent)))
    (is (= (:hash intent) (tx/intent-hash intent)))
    (is (re-find #"chain-id=1" (:hash intent)))
    (is (re-find #"origin=https://app.example" (:hash intent)))))

(deftest intent-hash-binds-payload-digest-not-raw-payload
  (let [intent (tx/tx->intent
                "intent:payload-private"
                {:kind :intent.kind/typed-data-sign
                 :chain-id 1
                 :account-id "acct:main"
                 :to (:address account)
                 :value "0"
                 :data "0x"
                 :origin "https://app.example"
                 :payload {:message {:contents "secret typed data"}}
                 :payload-hash "typed-data-v4:abc"
                 :payload-preview "payload:map:len=42"})]
    (is (not (re-find #"secret typed data" (:hash intent))))
    (is (not (re-find #"payload=" (:hash intent))))
    (is (re-find #"payload-hash=typed-data-v4:abc" (:hash intent)))
    (is (re-find #"payload-preview=payload:map:len=42" (:hash intent)))))

(deftest risk-catches-chain-and-approval-policy
  (let [state (ready-state)
        assessed (risk/assess state {:account-id "acct:main"
                                     :origin "https://app.example"
                                     :chain-id 8453
                                     :spender "0xunknown"
                                     :unlimited-approval? true})]
    (is (= :risk.level/high (:level assessed)))
    (is (contains? (set (map :risk (:risks assessed))) :risk/chain-not-selected))
    (is (contains? (set (map :risk (:risks assessed))) :risk/unknown-spender))
    (is (contains? (set (map :risk (:risks assessed))) :risk/unlimited-approval))))

(deftest swap-plan-uses-bounded-approval-before-router-call
  (let [request {:account-id "acct:main"
                 :origin "https://app.example"
                 :chain-id 1
                 :from-token "0xusdc"
                 :to-token "0xweth"
                 :amount-in "1000000"
                 :slippage-bps 50}
        quote {:provider :test-quote
               :id "quote:unit"
               :router "0xrouter"
               :spender "0xrouter"
               :calldata "0x1234"
               :min-amount-out "300000000000000"
               :deadline-ms 1782560300000
               :block-number 23000000}
        plan (swap/plan (ready-state) quote request)]
    (is (= [:intent.kind/erc20-approve :intent.kind/swap]
           (mapv :kind (:intents plan))))
    (is (= "1000000" (:amount (first (:intents plan)))))
    (is (= (:id quote) (:quote-id (first (:intents plan)))))
    (is (= (:id quote) (:quote-id (second (:intents plan)))))
    (is (false? (:unlimited-approval? (first (:intents plan)))))))

(deftest swap-allowance-compare-handles-uint256-decimal-strings
  (is (true? (swap/enough-allowance? swap/max-uint256 "1000000")))
  (is (true? (swap/enough-allowance? "0001000" "1000")))
  (is (false? (swap/enough-allowance? "999" "1000"))))

(def swap-request
  {:from-token "0xusdc"
   :to-token "0xweth"
   :amount-in "1000000"
   :slippage-bps 50})

(def swap-quote
  {:provider :test-quote
   :router "0xrouter"
   :spender "0xrouter"
   :calldata "0x1234"
   :min-amount-out "300000000000000"
   :deadline-ms 1782560300000
   :block-number 23000000})

(deftest actor-prepare-swap-creates-approval-and-router-intents
  (let [result (actor/step (ready-state)
                           [:wallet/prepare-swap
                            {:id "swap:intent"
                             :origin "https://app.example"
                             :request swap-request
                             :quote swap-quote}])
        intents (->> (:events result) (map second))]
    (is (= [:intent.kind/erc20-approve :intent.kind/swap]
           (mapv :kind intents)))
    (is (= 2 (count (:effects result))))
    (is (every? #(= :evm/simulate (:effect %)) (:effects result)))
    (is (= "0xrouter" (:spender (second intents))))
    (is (every? :quote-id intents))
    (is (re-find #"quote-id=quote:" (:hash (second intents))))
    (is (re-find #"deadline-ms=1782560300000" (:hash (second intents))))
    (is (some #(= ":wallet.intent/quote-id" (:a %)) (:datoms result)))
    (is (some #(= ":wallet.intent/deadline-ms" (:a %)) (:datoms result)))
    (is (some #(= ":wallet.intent/min-amount-out" (:a %)) (:datoms result)))
    (is (some #(= ":wallet.intent/hash" (:a %)) (:datoms result)))))

(deftest actor-prepare-swap-flags-expired-quote-from-explicit-clock
  (let [fresh (actor/step (ready-state)
                          [:wallet/prepare-swap
                           {:id "swap:fresh"
                            :origin "https://app.example"
                            :now-ms 1782560200000
                            :request swap-request
                            :quote swap-quote}])
        expired (actor/step (ready-state)
                            [:wallet/prepare-swap
                             {:id "swap:expired"
                              :origin "https://app.example"
                              :now-ms 1782560400000
                              :request swap-request
                              :quote swap-quote}])
        fresh-router-risk (get-in fresh [:effects 1 :risk])
        expired-router-risk (get-in expired [:effects 1 :risk])
        expired-risks (set (map :risk (:risks expired-router-risk)))]
    (is (= :risk.level/low (:level fresh-router-risk)))
    (is (= :risk.level/high (:level expired-router-risk)))
    (is (contains? expired-risks :risk/quote-expired))
    (is (re-find #"now-ms=1782560400000"
                 (get-in expired [:state :intents "swap:expired:1" :hash])))
    (is (some #(= ":wallet.intent/now-ms" (:a %)) (:datoms expired)))))

(deftest actor-prepare-swap-flags-quote-request-mismatch
  (let [mismatched-quote (assoc swap-quote
                                :from-token "0xdai"
                                :to-token "0xwbtc"
                                :amount-in "2000000")
        result (actor/step (ready-state)
                           [:wallet/prepare-swap
                            {:id "swap:mismatch"
                             :origin "https://app.example"
                             :request swap-request
                             :quote mismatched-quote}])
        router-risk (get-in result [:effects 1 :risk])
        router-intent (get-in result [:state :intents "swap:mismatch:1"])
        mismatch-risk (first (filter #(= :risk/quote-request-mismatch (:risk %))
                                     (:risks router-risk)))]
    (is (= :risk.level/high (:level router-risk)))
    (is (= [:from-token :to-token :amount-in] (:fields mismatch-risk)))
    (is (= [:from-token :to-token :amount-in] (:quote-mismatch-fields router-intent)))
    (is (re-find #"quote-mismatch-fields=" (:hash router-intent)))
    (is (some #(= ":wallet.intent/quote-mismatch-fields" (:a %)) (:datoms result)))))

(deftest actor-rejects-swap-quotes-with-missing-provenance
  (let [prepare-error (try
                        (actor/step (ready-state)
                                    [:wallet/prepare-swap
                                     {:id "swap:missing-quote-fields"
                                      :origin "https://app.example"
                                      :request swap-request
                                      :quote (dissoc swap-quote :router :deadline-ms)}])
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        observed-error (try
                         (actor/step (ready-state)
                                     [:wallet/quote-observed
                                      (-> (merge {:origin "https://app.example"
                                                  :account-id "acct:main"
                                                  :chain-id 1}
                                                 swap-request
                                                 swap-quote)
                                          (dissoc :account-id :spender :block-number))])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))]
    (is (= :wallet.quote/missing-fields (:kind prepare-error)))
    (is (= [:router :deadline-ms] (:missing prepare-error)))
    (is (= :wallet.quote/missing-fields (:kind observed-error)))
    (is (= [:account-id :spender :block-number] (:missing observed-error)))))

(deftest actor-prepare-contract-call-produces-simulation-effect-and-datoms
  (let [result (actor/step (ready-state)
                           [:wallet/prepare-contract-call
                            {:id "intent:call:1"
                             :to "0xdef0000000000000000000000000000000000000"
                             :value "0"
                             :data "0x"
                             :origin "https://app.example"}])]
    (is (= :intent.status/pending-user
           (get-in result [:state :intents "intent:call:1" :status])))
    (is (= :evm/simulate (get-in result [:effects 0 :effect])))
    (is (some #(= ":wallet.intent/hash" (:a %)) (:datoms result)))))

(deftest actor-refuses-duplicate-intent-ids
  (let [prepared (actor/step (ready-state)
                             [:wallet/prepare-contract-call
                              {:id "intent:dup:1"
                               :to "0xdef0000000000000000000000000000000000000"
                               :value "0"
                               :data "0x"
                               :origin "https://app.example"}])
        duplicate-call (try
                         (actor/step (:state prepared)
                                     [:wallet/prepare-contract-call
                                      {:id "intent:dup:1"
                                       :to "0xabc0000000000000000000000000000000000000"
                                       :value "1"
                                       :data "0x"
                                       :origin "https://app.example"}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        duplicate-swap-state (assoc-in (ready-state)
                                       [:intents "swap:dup:0"]
                                       {:id "swap:dup:0"
                                        :status :intent.status/pending-user})
        duplicate-swap (try
                         (actor/step duplicate-swap-state
                                     [:wallet/prepare-swap
                                      {:id "swap:dup"
                                       :origin "https://app.example"
                                       :request swap-request
                                       :quote swap-quote}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))]
    (is (= "intent:dup:1" (:id duplicate-call)))
    (is (= "swap:dup:0" (:id duplicate-swap)))
    (is (= "0xdef0000000000000000000000000000000000000"
           (get-in prepared [:state :intents "intent:dup:1" :to])))))

(deftest actor-prepare-native-transfer-creates-auditable-intent
  (let [result (actor/step (ready-state)
                           [:wallet/prepare-transfer
                            {:id "transfer:native:1"
                             :origin "https://app.example"
                             :asset :native
                             :to "0xdef0000000000000000000000000000000000000"
                             :amount "10000000000000000"}])
        intent (get-in result [:state :intents "transfer:native:1"])]
    (is (= :intent.kind/native-transfer (:kind intent)))
    (is (= "10000000000000000" (:value intent)))
    (is (= "0xdef0000000000000000000000000000000000000" (:recipient intent)))
    (is (re-find #"amount=10000000000000000" (:hash intent)))
    (is (= :evm/simulate (get-in result [:effects 0 :effect])))
    (is (some #(= ":wallet.intent/recipient" (:a %)) (:datoms result)))))

(deftest provider-prepare-erc20-transfer-returns-intent-id
  (let [result (provider/request (ready-state) "https://app.example"
                                 {:method "wallet_prepareTransfer"
                                  :params [{:token "0xusdc"
                                            :to "0xdef0000000000000000000000000000000000000"
                                            :amount "1000000"}]})
        intent-id (:result result)
        intent (get-in result [:state :intents intent-id])]
    (is (re-find #"^transfer:" intent-id))
    (is (= :intent.kind/erc20-transfer (:kind intent)))
    (is (= "0xusdc" (:token intent)))
    (is (= "1000000" (:amount intent)))
    (is (re-find #"token=0xusdc" (:hash intent)))
    (is (some #(= ":wallet.intent/token" (:a %)) (:datoms result)))))

(deftest actor-revoke-approval-creates-zero-approval-intent
  (let [result (actor/step (ready-state)
                           [:wallet/revoke-approval
                            {:id "revoke:1"
                             :origin "https://app.example"
                             :token "0xusdc"
                             :spender "0xunknown-spender"}])
        intent (get-in result [:state :intents "revoke:1"])
        risk-result (get-in result [:effects 0 :risk])]
    (is (= :intent.kind/erc20-revoke-approval (:kind intent)))
    (is (= "0xusdc" (:to intent)))
    (is (= "0xusdc" (:token intent)))
    (is (= "0xunknown-spender" (:spender intent)))
    (is (= "0" (:amount intent)))
    (is (= "0" (:value intent)))
    (is (re-find #"amount=0" (:hash intent)))
    (is (= :risk.level/low (:level risk-result)))
    (is (not-any? #(= :risk/unknown-spender (:risk %)) (:risks risk-result)))
    (is (= :evm/simulate (get-in result [:effects 0 :effect])))
    (is (some #(= ":wallet.intent/spender" (:a %)) (:datoms result)))))

(deftest actor-replay-validates-intent-preparation-commands-before-datoms
  (let [missing-call-id (try
                          (actor/step (ready-state)
                                      [:wallet/prepare-contract-call
                                       {:to "0xdef0000000000000000000000000000000000000"
                                        :value "0"
                                        :data "0x"
                                        :origin "https://app.example"}])
                          (catch clojure.lang.ExceptionInfo e
                            (ex-data e)))
        bad-call-data (try
                        (actor/step (ready-state)
                                    [:wallet/prepare-contract-call
                                     {:id "intent:bad-data"
                                      :to "0xdef0000000000000000000000000000000000000"
                                      :value "0"
                                      :data "transfer()"
                                      :origin "https://app.example"}])
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        bad-transfer-amount (try
                              (actor/step (ready-state)
                                          [:wallet/prepare-transfer
                                           {:id "transfer:bad-amount"
                                            :origin "https://app.example"
                                            :asset :native
                                            :to "0xdef0000000000000000000000000000000000000"
                                            :amount "0x10"}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        bad-transfer-chain (try
                             (actor/step (ready-state)
                                         [:wallet/prepare-transfer
                                          {:id "transfer:bad-chain"
                                           :origin "https://app.example"
                                           :asset :native
                                           :chain-id 0
                                           :to "0xdef0000000000000000000000000000000000000"
                                           :amount "10"}])
                             (catch clojure.lang.ExceptionInfo e
                               (ex-data e)))
        bad-revoke-token (try
                           (actor/step (ready-state)
                                       [:wallet/revoke-approval
                                        {:id "revoke:bad-token"
                                         :origin "https://app.example"
                                         :token "usdc"
                                         :spender "0xrouter"}])
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))]
    (is (= :wallet.contract-call/missing-fields (:kind missing-call-id)))
    (is (= [:id] (:missing missing-call-id)))
    (is (= :wallet.contract-call/data (:kind bad-call-data)))
    (is (= "transfer()" (:actual bad-call-data)))
    (is (= :wallet.transfer/amount (:kind bad-transfer-amount)))
    (is (= "0x10" (:actual bad-transfer-amount)))
    (is (= :wallet.transfer/missing-fields (:kind bad-transfer-chain)))
    (is (= :chain-id (:field bad-transfer-chain)))
    (is (= 0 (:actual bad-transfer-chain)))
    (is (= :wallet.revoke/token (:kind bad-revoke-token)))
    (is (= "usdc" (:actual bad-revoke-token)))))

(deftest provider-revoke-approval-returns-intent-id
  (let [result (provider/request (ready-state) "https://app.example"
                                 {:method "wallet_revokeApproval"
                                  :params [{:token "0xusdc"
                                            :spender "0xrouter"}]})
        intent-id (:result result)
        intent (get-in result [:state :intents intent-id])]
    (is (re-find #"^revoke:" intent-id))
    (is (= :intent.kind/erc20-revoke-approval (:kind intent)))
    (is (= "0xrouter" (:spender intent)))
    (is (= "0" (:amount intent)))
    (is (some #(= ":wallet.intent/spender" (:a %)) (:datoms result)))))

(deftest provider-returns-accounts-and-chain
  (let [state (ready-state)]
    (is (= ["0xabc0000000000000000000000000000000000000"]
           (:result (provider/request state "https://app.example"
                                      {:method "eth_accounts" :params []}))))
    (is (= "0x1"
           (:result (provider/request state "https://app.example"
                                      {:method "eth_chainId" :params []}))))))

(deftest provider-events-are-derived-from-pure-transitions
  (let [state (ready-state)
        same-account (actor/step state
                                 [:wallet/connect
                                  {:account account
                                   :origin "https://app.example"
                                   :chains [1]
                                   :requested [:eth/accounts :eth/call]}])
        other-state (-> state
                        (actor/apply-event [:account/connected other-account])
                        (actor/apply-event [:policy/granted
                                            {:origin "https://app.example"
                                             :accounts ["acct:other"]
                                             :chains [1]
                                             :caps #{:eth/accounts :eth/call}}]))]
    (is (= [["accountsChanged" ["0xabc0000000000000000000000000000000000000"]]]
           (provider/provider-events state state
                                     {:origin "https://app.example"
                                      :method "eth_requestAccounts"})))
    (is (= []
           (provider/provider-events state (:state same-account)
                                     (assoc same-account
                                            :origin "https://app.example"
                                            :method "eth_call"))))
      (is (= [["accountsChanged" ["0xbbb0000000000000000000000000000000000000"]]]
           (provider/provider-events state other-state
                                      {:origin "https://app.example"
                                       :method "eth_call"
                                       :events [[:account/connected other-account]]})))))

(deftest actor-replay-validates-connect-command-before-datoms
  (let [missing-origin (try
                         (actor/step actor/empty-state
                                     [:wallet/connect
                                      {:account account
                                       :chains [1]
                                       :requested [:eth/accounts]}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        bad-account-address (try
                              (actor/step actor/empty-state
                                          [:wallet/connect
                                           {:account (assoc account :address "0xAlice")
                                            :origin "https://app.example"
                                            :chains [1]
                                            :requested [:eth/accounts]}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        bad-chains (try
                     (actor/step actor/empty-state
                                 [:wallet/connect
                                  {:account account
                                   :origin "https://app.example"
                                   :chains [0]
                                   :requested [:eth/accounts]}])
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))
        bad-requested (try
                        (actor/step actor/empty-state
                                    [:wallet/connect
                                     {:account account
                                      :origin "https://app.example"
                                      :chains [1]
                                      :requested ["eth_accounts"]}])
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        bad-slippage (try
                       (actor/step actor/empty-state
                                   [:wallet/connect
                                    {:account account
                                     :origin "https://app.example"
                                     :chains [1]
                                     :requested [:eth/accounts]
                                     :max-slippage-bps 10001}])
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))]
    (is (= :wallet.connect/missing-fields (:kind missing-origin)))
    (is (= [:origin] (:missing missing-origin)))
    (is (= :wallet.connect/account-address (:kind bad-account-address)))
    (is (= "0xAlice" (:actual bad-account-address)))
    (is (= :wallet.connect/chains (:kind bad-chains)))
    (is (= [0] (:actual bad-chains)))
    (is (= :wallet.connect/requested (:kind bad-requested)))
    (is (= ["eth_accounts"] (:actual bad-requested)))
    (is (= :wallet.connect/max-slippage-bps (:kind bad-slippage)))
    (is (= 10001 (:actual bad-slippage)))))

(deftest provider-replaced-state-events-are-derived-from-pure-states
  (let [state (ready-state)
        switched (-> state
                     (actor/apply-event [:network/added base-network])
                     (actor/apply-event [:network/selected {:chain-id 8453}]))
        changed-account (-> switched
                            (actor/apply-event [:account/connected other-account])
                            (actor/apply-event [:policy/granted
                                                {:origin "https://app.example"
                                                 :accounts ["acct:other"]
                                                 :chains [1 8453]
                                                 :caps #{:eth/accounts :eth/call}}]))]
    (is (= []
           (provider/provider-replaced-state-events state state "https://app.example")))
    (is (= [["chainChanged" "0x2105"]]
           (provider/provider-replaced-state-events state switched "https://app.example")))
    (is (= [["chainChanged" "0x2105"]
            ["accountsChanged" ["0xbbb0000000000000000000000000000000000000"]]]
           (provider/provider-replaced-state-events state changed-account "https://app.example")))))

(deftest provider-event-derivation-rejects-malformed-selected-chain
  (let [state (ready-state)
        malformed (assoc state :selected-chain-id nil)
        request-error (try
                        (provider/provider-events state malformed
                                                  {:origin "https://app.example"
                                                   :method "eth_call"})
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        replacement-error (try
                            (provider/provider-replaced-state-events state
                                                                     malformed
                                                                     "https://app.example")
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))]
    (is (= -32602 (:code request-error)))
    (is (= :invalid-params (:error-kind request-error)))
    (is (= "eth_call" (:method request-error)))
    (is (= :invalid-selected-chain-id (:reason request-error)))
    (is (= -32602 (:code replacement-error)))
    (is (= :invalid-params (:error-kind replacement-error)))
    (is (= "provider.setState" (:method replacement-error)))
    (is (= :invalid-selected-chain-id (:reason replacement-error)))))

(deftest provider-switch-add-watch-and-rpc-effects
  (let [state (ready-state)
        added (provider/request state "https://app.example"
                                {:method "wallet_addEthereumChain"
                                 :params [{:chainId "0x2105"
                                           :chainName "Base"
                                           :nativeCurrency {:symbol "ETH"}
                                           :rpcUrls ["https://base.example"]}]})
        switched (provider/request (:state added) "https://app.example"
                                   {:method "wallet_switchEthereumChain"
                                    :params [{:chainId "0x2105"}]})
        watched (provider/request (:state switched) "https://app.example"
                                  {:method "wallet_watchAsset"
                                   :params [{:type "ERC20"
                                             :options {:address "0x0000000000000000000000000000000000000abc"
                                                       :symbol "USDC"
                                                       :decimals 6}}]})
        call (provider/request (:state watched) "https://app.example"
                               {:method "eth_call"
                                :params [{:to "0xdef" :data "0x1234"} "latest"]})]
    (is (= 8453 (get-in switched [:state :selected-chain-id])))
    (is (= true (:result watched)))
    (is (= :evm-rpc/call (get-in call [:effects 0 :effect])))
    (is (= 8453 (get-in call [:effects 0 :chain-id])))))

(deftest provider-add-chain-validates-network-payload-before-state
  (let [invalid-chain-id (try
                           (provider/request (ready-state) "https://app.example"
                                             {:method "wallet_addEthereumChain"
                                              :params [{:chainId "0xzz"
                                                        :chainName "Broken"
                                                        :nativeCurrency {:symbol "ETH"}
                                                        :rpcUrls ["https://base.example"]}]})
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))
        missing-name (try
                       (provider/request (ready-state) "https://app.example"
                                         {:method "wallet_addEthereumChain"
                                          :params [{:chainId "0x2105"
                                                    :nativeCurrency {:symbol "ETH"}
                                                    :rpcUrls ["https://base.example"]}]})
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))
        missing-native (try
                         (provider/request (ready-state) "https://app.example"
                                           {:method "wallet_addEthereumChain"
                                            :params [{:chainId "0x2105"
                                                      :chainName "Base"
                                                      :rpcUrls ["https://base.example"]}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        missing-symbol (try
                         (provider/request (ready-state) "https://app.example"
                                           {:method "wallet_addEthereumChain"
                                            :params [{:chainId "0x2105"
                                                      :chainName "Base"
                                                      :nativeCurrency {}
                                                      :rpcUrls ["https://base.example"]}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        missing-rpc (try
                      (provider/request (ready-state) "https://app.example"
                                        {:method "wallet_addEthereumChain"
                                         :params [{:chainId "0x2105"
                                                   :chainName "Base"
                                                   :nativeCurrency {:symbol "ETH"}}]})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        invalid-rpc (try
                      (provider/request (ready-state) "https://app.example"
                                        {:method "wallet_addEthereumChain"
                                         :params [{:chainId "0x2105"
                                                   :chainName "Base"
                                                   :nativeCurrency {:symbol "ETH"}
                                                   :rpcUrls ["not-a-url"]}]})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))]
    (is (= -32602 (:code invalid-chain-id)))
    (is (= :invalid-chain-id (:reason invalid-chain-id)))
    (is (= -32602 (:code missing-name)))
    (is (= :invalid-chain-name (:reason missing-name)))
    (is (= -32602 (:code missing-native)))
    (is (= :native-currency-must-be-map (:reason missing-native)))
    (is (= -32602 (:code missing-symbol)))
    (is (= :missing-native-currency-symbol (:reason missing-symbol)))
    (is (= -32602 (:code missing-rpc)))
    (is (= :invalid-rpc-urls (:reason missing-rpc)))
    (is (= -32602 (:code invalid-rpc)))
    (is (= :invalid-rpc-urls (:reason invalid-rpc)))))

(deftest actor-replay-validates-network-and-asset-commands-before-datoms
  (let [bad-network-missing (try
                              (actor/step (ready-state)
                                          [:wallet/add-network {:chain-id 8453
                                                                :name "Base"
                                                                :native-symbol "ETH"}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        bad-network-chain (try
                            (actor/step (ready-state)
                                        [:wallet/add-network {:chain-id 0
                                                              :name "Base"
                                                              :native-symbol "ETH"
                                                              :rpc-ref "provider:8453"}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        bad-network-name (try
                           (actor/step (ready-state)
                                       [:wallet/add-network {:chain-id 8453
                                                             :name ""
                                                             :native-symbol "ETH"
                                                             :rpc-ref "provider:8453"}])
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))
        bad-asset-missing (try
                            (actor/step (ready-state)
                                        [:wallet/watch-asset {:chain-id 1
                                                              :kind :asset.kind/erc20
                                                              :address "0x0000000000000000000000000000000000000abc"
                                                              :symbol "USDC"}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        bad-asset-address (try
                            (actor/step (ready-state)
                                        [:wallet/watch-asset {:chain-id 1
                                                              :kind :asset.kind/erc20
                                                              :address "0xUSDC"
                                                              :symbol "USDC"
                                                              :decimals 6}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        bad-asset-kind (try
                         (actor/step (ready-state)
                                     [:wallet/watch-asset {:chain-id 1
                                                           :kind :asset.kind/erc777
                                                           :address "0x0000000000000000000000000000000000000abc"
                                                           :symbol "TOK"
                                                           :decimals 18}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        bad-asset-decimals (try
                             (actor/step (ready-state)
                                         [:wallet/watch-asset {:chain-id 1
                                                               :kind :asset.kind/erc20
                                                               :address "0x0000000000000000000000000000000000000abc"
                                                               :symbol "USDC"
                                                               :decimals "6"}])
                             (catch clojure.lang.ExceptionInfo e
                               (ex-data e)))]
    (is (= :wallet.network/missing-fields (:kind bad-network-missing)))
    (is (= [:rpc-ref] (:missing bad-network-missing)))
    (is (= :wallet.network/chain-id (:kind bad-network-chain)))
    (is (= 0 (:actual bad-network-chain)))
    (is (= :wallet.network/name (:kind bad-network-name)))
    (is (= "" (:actual bad-network-name)))
    (is (= :wallet.asset/missing-fields (:kind bad-asset-missing)))
    (is (= [:decimals] (:missing bad-asset-missing)))
    (is (= :wallet.asset/address (:kind bad-asset-address)))
    (is (= "0xUSDC" (:actual bad-asset-address)))
    (is (= :wallet.asset/kind (:kind bad-asset-kind)))
    (is (= :asset.kind/erc777 (:actual bad-asset-kind)))
    (is (= :wallet.asset/decimals (:kind bad-asset-decimals)))
    (is (= "6" (:actual bad-asset-decimals)))))

(deftest actor-replay-validates-state-transition-commands-before-datoms
  (let [prepared (actor/step (ready-state)
                             [:wallet/prepare-contract-call
                              {:id "intent:decision-validation"
                               :to "0xdef0000000000000000000000000000000000000"
                               :value "0"
                               :data "0x"
                               :origin "https://app.example"}])
        bad-select-missing (try
                             (actor/step (ready-state) [:wallet/select-network {}])
                             (catch clojure.lang.ExceptionInfo e
                               (ex-data e)))
        bad-select-chain (try
                           (actor/step (ready-state) [:wallet/select-network {:chain-id 0}])
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))
        bad-approve-missing (try
                              (actor/step (:state prepared) [:wallet/approve-intent {}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        bad-approve-id (try
                         (actor/step (:state prepared) [:wallet/approve-intent {:id ""}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        bad-approve-ack (try
                          (actor/step (:state prepared)
                                      [:wallet/approve-intent {:id "intent:decision-validation"
                                                               :risk-acknowledged? "yes"}])
                          (catch clojure.lang.ExceptionInfo e
                            (ex-data e)))
        bad-reject-reason (try
                            (actor/step (:state prepared)
                                        [:wallet/reject-intent {:id "intent:decision-validation"
                                                                :reason ""}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))]
    (is (= :wallet.select-network/missing-fields (:kind bad-select-missing)))
    (is (= [:chain-id] (:missing bad-select-missing)))
    (is (= :wallet.select-network/chain-id (:kind bad-select-chain)))
    (is (= 0 (:actual bad-select-chain)))
    (is (= :wallet.approve-intent/missing-fields (:kind bad-approve-missing)))
    (is (= [:id] (:missing bad-approve-missing)))
    (is (= :wallet.approve-intent/missing-fields (:kind bad-approve-id)))
    (is (= "" (:actual bad-approve-id)))
    (is (= :wallet.approve-intent/risk-acknowledged? (:kind bad-approve-ack)))
    (is (= "yes" (:actual bad-approve-ack)))
    (is (= :wallet.reject-intent/reason (:kind bad-reject-reason)))
    (is (= "" (:actual bad-reject-reason)))))

(deftest runtime-runs-evm-rpc-call-and-estimate-gas-effects
  (let [seen (atom [])
        env {:evm-rpc-fn (fn [request]
                           (swap! seen conj request)
                           (case (:method request)
                             "eth_call" "0x2a"
                             "eth_estimateGas" "0x5208"))}
        call (runtime/run-effect env {:effect :evm-rpc/call
                                      :chain-id 1
                                      :params [{:to "0xdef" :data "0x1234"} "latest"]})
        estimate (runtime/run-effect env {:effect :evm-rpc/estimate-gas
                                          :chain-id 8453
                                          :params [{:to "0xdef" :data "0x"}]})]
    (is (= "0x2a" (:result call)))
    (is (= "0x5208" (:result estimate)))
    (is (= [] (:commands call)))
    (is (= [{:method "eth_call"
             :chain-id 1
             :params [{:to "0xdef" :data "0x1234"} "latest"]}
            {:method "eth_estimateGas"
             :chain-id 8453
             :params [{:to "0xdef" :data "0x"}]}]
           @seen))))

(deftest provider-denies-chain-outside-origin-policy
  (let [state (-> (ready-state)
                  (actor/apply-event [:network/added {:chain-id 8453
                                                      :name "Base"
                                                      :namespace "eip155"
                                                      :native-symbol "ETH"
                                                      :rpc-ref "rpc:base"
                                                      :status :network.status/enabled}])
                  (assoc-in [:policies "https://chain-limited.example"]
                            {:origin "https://chain-limited.example"
                             :accounts ["acct:main"]
                             :chains [1]
                             :caps #{:eth/accounts :eth/chain-id :eth/switch-chain
                                     :eth/call :eth/send-tx :eth/prepare-transfer
                                     :eth/revoke-approval :eth/quote-swap :eth/prepare-swap}}))
        switch-error (try
                       (provider/request state "https://chain-limited.example"
                                         {:method "wallet_switchEthereumChain"
                                          :params [{:chainId "0x2105"}]})
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))
        call-error (try
                     (provider/request (assoc state :selected-chain-id 8453)
                                       "https://chain-limited.example"
                                       {:method "eth_call"
                                        :params [{:to "0xdef" :data "0x1234"} "latest"]})
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))
        transfer-error (try
                         (provider/request state "https://chain-limited.example"
                                           {:method "wallet_prepareTransfer"
                                            :params [{:chain-id 8453
                                                      :token "0xusdc"
                                                      :to "0xdef0000000000000000000000000000000000000"
                                                      :amount "1000000"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        rpc-param-chain-error (try
                                (provider/request state "https://chain-limited.example"
                                                  {:method "eth_call"
                                                   :params [{:to "0xdef"
                                                             :data "0x1234"
                                                             :chainId "0x2105"}
                                                            "latest"]})
                                (catch clojure.lang.ExceptionInfo e
                                  (ex-data e)))
        quote-error (try
                      (provider/request state "https://chain-limited.example"
                                        {:method "wallet_quoteSwap"
                                         :params [(assoc swap-request :chain-id 8453)]})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        nested-swap-error (try
                            (provider/request state "https://chain-limited.example"
                                              {:method "wallet_prepareSwap"
                                               :params [{:request (assoc swap-request :chain-id 8453)
                                                         :quote swap-quote}]})
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))]
    (is (= 4100 (:code switch-error)))
    (is (= :unauthorized (:error-kind switch-error)))
    (is (= 8453 (:chain-id switch-error)))
    (is (= 4100 (:code call-error)))
    (is (= 8453 (:chain-id call-error)))
    (is (= 4100 (:code transfer-error)))
    (is (= 8453 (:chain-id transfer-error)))
    (is (= 4100 (:code rpc-param-chain-error)))
    (is (= 8453 (:chain-id rpc-param-chain-error)))
    (is (= 4100 (:code quote-error)))
    (is (= 8453 (:chain-id quote-error)))
    (is (= 4100 (:code nested-swap-error)))
    (is (= 8453 (:chain-id nested-swap-error)))))

(deftest provider-denies-account-outside-origin-policy
  (let [state (-> (ready-state)
                  (actor/apply-event [:account/connected other-account])
                  (assoc :selected-account-id "acct:main")
                  (assoc-in [:policies "https://acct-limited.example"]
                            {:origin "https://acct-limited.example"
                             :accounts ["acct:main"]
                             :chains [1]
                             :caps #{:eth/accounts :eth/chain-id :eth/send-tx
                                     :eth/estimate-gas :eth/prepare-transfer :eth/sign-message
                                     :eth/sign-typed-data :eth/quote-swap
                                     :eth/prepare-swap}}))
        tx-error (try
                   (provider/request state "https://acct-limited.example"
                                     {:method "eth_sendTransaction"
                                      :params [{:from (:address other-account)
                                                :to "0xdef0000000000000000000000000000000000000"
                                                :value "0x0"
                                                :data "0x"}]})
                   (catch clojure.lang.ExceptionInfo e
                     (ex-data e)))
        transfer-error (try
                         (provider/request state "https://acct-limited.example"
                                           {:method "wallet_prepareTransfer"
                                            :params [{:account-id "acct:other"
                                                      :token "0xusdc"
                                                      :to "0xdef0000000000000000000000000000000000000"
                                                      :amount "1000000"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        sign-error (try
                     (provider/request state "https://acct-limited.example"
                                       {:method "personal_sign"
                                        :params ["0x68656c6c6f" (:address other-account)]})
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))
        typed-error (try
                      (provider/request state "https://acct-limited.example"
                                        {:method "eth_signTypedData_v4"
                                         :params [(:address other-account)
                                                  {:domain {:name "Kotoba" :chainId 1}
                                                   :message {:contents "hello"}}]})
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        rpc-from-error (try
                         (provider/request state "https://acct-limited.example"
                                           {:method "eth_estimateGas"
                                            :params [{:from (:address other-account)
                                                      :to "0xdef0000000000000000000000000000000000000"
                                                      :data "0x"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        quote-error (try
                      (provider/request state "https://acct-limited.example"
                                        {:method "wallet_quoteSwap"
                                         :params [(assoc swap-request :account-id "acct:other")]})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        nested-swap-error (try
                            (provider/request state "https://acct-limited.example"
                                              {:method "wallet_prepareSwap"
                                               :params [{:request (assoc swap-request :account-id "acct:other")
                                                         :quote swap-quote}]})
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))]
    (is (= 4100 (:code tx-error)))
    (is (= (:address other-account) (:address tx-error)))
    (is (= 4100 (:code transfer-error)))
    (is (= "acct:other" (:account-id transfer-error)))
    (is (= 4100 (:code sign-error)))
    (is (= (:address other-account) (:address sign-error)))
    (is (= 4100 (:code typed-error)))
    (is (= (:address other-account) (:address typed-error)))
    (is (= 4100 (:code rpc-from-error)))
    (is (= (:address other-account) (:address rpc-from-error)))
    (is (= 4100 (:code quote-error)))
    (is (= "acct:other" (:account-id quote-error)))
    (is (= 4100 (:code nested-swap-error)))
    (is (= "acct:other" (:account-id nested-swap-error)))))

(deftest provider-rpc-params-are-validated-before-host-effects
  (let [call-error (try
                     (provider/request (ready-state) "https://app.example"
                                       {:method "eth_call"
                                        :params ["not-a-tx-object" "latest"]})
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))
        estimate-error (try
                         (provider/request (ready-state) "https://app.example"
                                           {:method "eth_estimateGas"
                                            :params [{:to "0xdef"
                                                      :chainId "not-a-chain"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))]
    (is (= -32602 (:code call-error)))
    (is (= :first-param-must-be-map (:reason call-error)))
    (is (= -32602 (:code estimate-error)))
    (is (= :invalid-chain-id (:reason estimate-error)))))

(deftest provider-denies-unregistered-target-chain-before-effects
  (let [allowed-but-unregistered 8453
        unregistered-state (assoc (ready-state) :selected-chain-id allowed-but-unregistered)
        rpc-error (try
                    (provider/request (ready-state) "https://app.example"
                                      {:method "eth_call"
                                       :params [{:to "0xdef"
                                                 :data "0x1234"
                                                 :chain-id allowed-but-unregistered}
                                                "latest"]})
                    (catch clojure.lang.ExceptionInfo e
                      (ex-data e)))
        transfer-error (try
                         (provider/request (ready-state) "https://app.example"
                                           {:method "wallet_prepareTransfer"
                                            :params [{:chain-id allowed-but-unregistered
                                                      :to "0xdef0000000000000000000000000000000000000"
                                                      :amount "1000000"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        quote-error (try
                      (provider/request (ready-state) "https://app.example"
                                        {:method "wallet_quoteSwap"
                                         :params [(assoc swap-request
                                                         :chain-id allowed-but-unregistered)]})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        sign-error (try
                     (provider/request unregistered-state "https://app.example"
                                       {:method "personal_sign"
                                        :params ["0x68656c6c6f" (:address account)]})
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))]
    (is (every? #(= 4902 (:code %))
                [rpc-error transfer-error quote-error sign-error]))
    (is (every? #(= :unknown-chain (:error-kind %))
                [rpc-error transfer-error quote-error sign-error]))
    (is (every? #(= allowed-but-unregistered (:chain-id %))
                [rpc-error transfer-error quote-error sign-error]))))

(deftest provider-denies-unregistered-or-mismatched-accounts-before-effects
  (let [ghost-state (-> (ready-state)
                        (assoc :selected-account-id "acct:ghost")
                        (assoc-in [:policies "https://ghost.example"]
                                  {:origin "https://ghost.example"
                                   :accounts ["acct:ghost"]
                                   :chains [1]
                                   :caps #{:eth/accounts :eth/chain-id :eth/send-tx
                                           :eth/prepare-transfer :eth/quote-swap
                                           :eth/sign-message}}))
        ghost-transfer (try
                         (provider/request ghost-state "https://ghost.example"
                                           {:method "wallet_prepareTransfer"
                                            :params [{:account-id "acct:ghost"
                                                      :to "0xdef0000000000000000000000000000000000000"
                                                      :amount "1000000"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        ghost-quote (try
                      (provider/request ghost-state "https://ghost.example"
                                        {:method "wallet_quoteSwap"
                                         :params [(assoc swap-request :account-id "acct:ghost")]})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        ghost-sign (try
                     (provider/request ghost-state "https://ghost.example"
                                       {:method "personal_sign"
                                        :params ["0x68656c6c6f" (:address account)]})
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))
        mismatch-error (try
                         (provider/request (-> (ready-state)
                                               (actor/apply-event [:account/connected other-account]))
                                           "https://app.example"
                                           {:method "eth_sendTransaction"
                                            :params [{:account-id "acct:main"
                                                      :from (:address other-account)
                                                      :to "0xdef0000000000000000000000000000000000000"
                                                      :data "0x"}]})
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        unknown-address (try
                          (provider/request (ready-state) "https://app.example"
                                            {:method "eth_estimateGas"
                                             :params [{:from "0x9990000000000000000000000000000000000000"
                                                       :to "0xdef0000000000000000000000000000000000000"
                                                       :data "0x"}]})
                          (catch clojure.lang.ExceptionInfo e
                            (ex-data e)))]
    (is (every? #(= 4100 (:code %))
                [ghost-transfer ghost-quote ghost-sign mismatch-error unknown-address]))
    (is (= "acct:ghost" (:account-id ghost-transfer)))
    (is (= "acct:ghost" (:account-id ghost-quote)))
    (is (= "acct:main" (:account-id ghost-sign)))
    (is (= (:address account) (:address ghost-sign)))
    (is (= "acct:other" (:address-account-id mismatch-error)))
    (is (= "0x9990000000000000000000000000000000000000" (:address unknown-address)))))

(deftest provider-send-transaction-creates-intent-not-raw-submit
  (let [result (provider/request (ready-state) "https://app.example"
                                 {:method "eth_sendTransaction"
                                  :params [{:from (:address account)
                                            :to "0xdef0000000000000000000000000000000000000"
                                            :value "0x0"
                                            :data "0x"}]})]
    (is (= nil (:result result)))
    (is (= :evm/simulate (get-in result [:effects 0 :effect])))
    (is (some #(= ":wallet.intent/status" (:a %)) (:datoms result)))))

(deftest provider-send-transaction-honors-explicit-from-account-and-chain
  (let [state (-> (ready-state)
                  (actor/apply-event [:account/connected other-account])
                  (actor/apply-event [:network/added {:chain-id 8453
                                                       :name "Base"
                                                       :namespace "eip155"
                                                       :native-symbol "ETH"
                                                       :rpc-ref "rpc:base"
                                                       :status :network.status/enabled}])
                  (actor/apply-event [:network/selected {:chain-id 1}])
                  (actor/apply-event [:policy/granted {:origin "https://app.example"
                                                       :accounts ["acct:main" "acct:other"]
                                                       :chains [1 8453]
                                                       :caps #{:eth/send-tx}}]))
        result (provider/request state "https://app.example"
                                 {:method "eth_sendTransaction"
                                  :params [{:from (:address other-account)
                                            :chainId "0x2105"
                                            :to "0xdef0000000000000000000000000000000000000"
                                            :value "0x0"
                                            :data "0x"}]})
        intent (first (vals (get-in result [:state :intents])))]
    (is (= "acct:other" (:account-id intent)))
    (is (= 8453 (:chain-id intent)))
    (is (= :evm/simulate (get-in result [:effects 0 :effect])))))

(deftest provider-personal-sign-creates-approval-intent
  (let [result (provider/request (ready-state) "https://app.example"
                                 {:method "personal_sign"
                                  :params ["0x68656c6c6f" (:address account)]})
        intent-id (:result result)
        intent (get-in result [:state :intents intent-id])]
    (is (re-find #"^sign:" intent-id))
    (is (= :intent.kind/message-sign (:kind intent)))
    (is (= (:address account) (:to intent)))
    (is (= "0x68656c6c6f" (:payload intent)))
    (is (re-find #"personal-sign:" (:payload-hash intent)))
    (is (some #(= ":wallet.intent/payload-hash" (:a %)) (:datoms result)))
    (is (= :wallet/review-signature (get-in result [:effects 0 :effect])))))

(deftest actor-replay-validates-signature-preparation-before-datoms
  (let [missing-payload (try
                          (actor/step (ready-state)
                                      [:wallet/prepare-signature
                                       {:id "sign:missing-payload"
                                        :kind :intent.kind/message-sign
                                        :origin "https://app.example"
                                        :chain-id 1
                                        :address (:address account)}])
                          (catch clojure.lang.ExceptionInfo e
                            (ex-data e)))
        bad-kind (try
                   (actor/step (ready-state)
                               [:wallet/prepare-signature
                                {:id "sign:bad-kind"
                                 :kind :intent.kind/raw-sign
                                 :origin "https://app.example"
                                 :chain-id 1
                                 :address (:address account)
                                 :payload "0x68656c6c6f"}])
                   (catch clojure.lang.ExceptionInfo e
                     (ex-data e)))
        bad-address (try
                      (actor/step (ready-state)
                                  [:wallet/prepare-signature
                                   {:id "sign:bad-address"
                                    :kind :intent.kind/message-sign
                                    :origin "https://app.example"
                                    :chain-id 1
                                    :address "0xAlice"
                                    :payload "0x68656c6c6f"}])
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        bad-chain (try
                    (actor/step (ready-state)
                                [:wallet/prepare-signature
                                 {:id "sign:bad-chain"
                                  :kind :intent.kind/message-sign
                                  :origin "https://app.example"
                                  :chain-id 0
                                  :address (:address account)
                                  :payload "0x68656c6c6f"}])
                    (catch clojure.lang.ExceptionInfo e
                      (ex-data e)))
        bad-payload-hash (try
                           (actor/step (ready-state)
                                       [:wallet/prepare-signature
                                        {:id "sign:bad-payload-hash"
                                         :kind :intent.kind/message-sign
                                         :origin "https://app.example"
                                         :chain-id 1
                                         :address (:address account)
                                         :payload "0x68656c6c6f"
                                         :payload-hash ""}])
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))]
    (is (= :wallet.signature/missing-fields (:kind missing-payload)))
    (is (= [:payload] (:missing missing-payload)))
    (is (= :wallet.signature/kind (:kind bad-kind)))
    (is (= :intent.kind/raw-sign (:actual bad-kind)))
    (is (= :wallet.signature/address (:kind bad-address)))
    (is (= "0xAlice" (:actual bad-address)))
    (is (= :wallet.signature/missing-fields (:kind bad-chain)))
    (is (= :chain-id (:field bad-chain)))
    (is (= 0 (:actual bad-chain)))
    (is (= :wallet.signature/payload-hash (:kind bad-payload-hash)))
    (is (= "" (:actual bad-payload-hash)))))

(deftest provider-signature-honors-explicit-address-account
  (let [state (-> (ready-state)
                  (actor/apply-event [:account/connected other-account])
                  (actor/apply-event [:network/selected {:chain-id 1}])
                  (actor/apply-event [:policy/granted {:origin "https://app.example"
                                                       :accounts ["acct:main" "acct:other"]
                                                       :chains [1]
                                                       :caps #{:eth/sign-message
                                                               :eth/sign-typed-data}}]))
        personal (provider/request state "https://app.example"
                                   {:method "personal_sign"
                                    :params ["0x68656c6c6f" (:address other-account)]})
        typed (provider/request state "https://app.example"
                                {:method "eth_signTypedData_v4"
                                 :params [(:address other-account)
                                          {:domain {:name "Kotoba" :chainId 1}
                                           :message {:contents "hello"}}]})]
    (is (= "acct:other" (get-in personal [:state :intents (:result personal) :account-id])))
    (is (= "acct:other" (get-in typed [:state :intents (:result typed) :account-id])))))

(deftest provider-signature-params-must-identify-an-explicit-address
  (let [personal-no-address (try
                              (provider/request (ready-state) "https://app.example"
                                                {:method "personal_sign"
                                                 :params ["0x68656c6c6f" "hello"]})
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        personal-two-addresses (try
                                 (provider/request (ready-state) "https://app.example"
                                                   {:method "personal_sign"
                                                    :params [(:address account)
                                                             "0xdef0000000000000000000000000000000000000"]})
                                 (catch clojure.lang.ExceptionInfo e
                                   (ex-data e)))
        typed-no-address (try
                           (provider/request (ready-state) "https://app.example"
                                             {:method "eth_signTypedData_v4"
                                              :params ["not-an-address"
                                                       {:domain {:name "Kotoba"}
                                                        :message {:contents "hello"}}]})
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))]
    (is (= -32602 (:code personal-no-address)))
    (is (= :exactly-one-address-required (:reason personal-no-address)))
    (is (= -32602 (:code personal-two-addresses)))
    (is (= :exactly-one-address-required (:reason personal-two-addresses)))
    (is (= -32602 (:code typed-no-address)))
    (is (= :first-param-must-be-address (:reason typed-no-address)))))

(deftest provider-typed-data-sign-and-runtime-signature-lifecycle
  (let [typed-data {:domain {:name "Kotoba" :chainId 1}
                    :message {:contents "hello"}}
        prepared (provider/request (ready-state) "https://app.example"
                                   {:method "eth_signTypedData_v4"
                                    :params [(:address account) typed-data]})
        intent-id (:result prepared)
        approved (actor/step (:state prepared) [:wallet/approve-intent {:id intent-id}])
        effect (first (:effects approved))
        ran (runtime/run-effect
             {:clock-fn (constantly 1782560000700)
              :sign-message-fn (fn [intent]
                                 {:signature "0xsignedtyped"
                                  :payload-hash (:payload-hash intent)})}
             effect)
        applied (runtime/apply-commands (:state approved) (:commands ran))
        signature-id (get-in ran [:commands 0 1 :id])]
    (is (= :intent.kind/typed-data-sign
           (get-in prepared [:state :intents intent-id :kind])))
    (is (= :wallet/sign-message (:effect effect)))
    (is (re-find #"typed-data-v4:" (get-in prepared [:state :intents intent-id :payload-hash])))
    (is (not (re-find #"payload=" (get-in prepared [:state :intents intent-id :hash]))))
    (is (re-find #"payload-preview=payload:map:len="
                 (get-in prepared [:state :intents intent-id :hash])))
    (is (re-find #"^payload:map:len="
                 (get-in prepared [:state :intents intent-id :payload-preview])))
    (is (some #(= ":wallet.intent/payload-hash" (:a %)) (:datoms prepared)))
    (is (some #(= ":wallet.intent/payload-preview" (:a %)) (:datoms prepared)))
    (is (not-any? #(re-find #"contents" (str %)) (:datoms prepared)))
    (is (= "0xsignedtyped" (get-in applied [:state :signatures signature-id :signature])))
    (is (= :intent.status/signed
           (get-in applied [:state :intents intent-id :status])))
    (is (some #(= ":wallet.signature/signature" (:a %)) (:datoms applied)))
    (is (some #(= ":wallet.signature/payload-hash" (:a %)) (:datoms applied)))
    (is (some #(and (= ":wallet.intent/status" (:a %))
                    (= ":intent.status/signed" (:v_edn %)))
              (:datoms applied)))))

(deftest provider-prepare-swap-returns-created-intent-ids
  (let [result (provider/request (ready-state) "https://app.example"
                                 {:method "wallet_prepareSwap"
                                  :params [{:request swap-request
                                            :quote swap-quote}]})]
    (is (= 2 (count (:result result))))
    (is (= 2 (count (:effects result))))
    (is (every? #(re-find #"^swap:" %) (:result result)))))

(deftest provider-prepare-swap-honors-nested-request-account-and-chain
  (let [state (-> (ready-state)
                  (actor/apply-event [:account/connected other-account])
                  (actor/apply-event [:network/added {:chain-id 8453
                                                       :name "Base"
                                                       :namespace "eip155"
                                                       :native-symbol "ETH"
                                                       :rpc-ref "rpc:base"
                                                       :status :network.status/enabled}])
                  (actor/apply-event [:network/selected {:chain-id 1}])
                  (actor/apply-event [:policy/granted {:origin "https://app.example"
                                                       :accounts ["acct:main" "acct:other"]
                                                       :chains [1 8453]
                                                       :caps #{:eth/prepare-swap}}]))
        result (provider/request state "https://app.example"
                                 {:method "wallet_prepareSwap"
                                  :params [{:request (assoc swap-request
                                                            :from (:address other-account)
                                                            :chainId "0x2105")
                                            :quote swap-quote}]})
        intents (vals (get-in result [:state :intents]))]
    (is (= #{"acct:other"} (set (map :account-id intents))))
    (is (= #{8453} (set (map :chain-id intents))))
    (is (= 2 (count (:effects result))))))

(deftest provider-and-runtime-quote-swap-through-host-capability
  (let [state (actor/apply-event (ready-state)
                                 [:network/added {:chain-id 8453
                                                  :name "Base"
                                                  :namespace "eip155"
                                                  :native-symbol "ETH"
                                                  :rpc-ref "rpc:base"
                                                  :status :network.status/enabled}])
        quoted (provider/request state "https://app.example"
                                 {:method "wallet_quoteSwap"
                                  :params [(assoc swap-request :chain-id 8453)]})
        ran (runtime/run-effect
             {:clock-fn (constantly 1782560000400)
              :quote-fn (fn [request]
                          (assoc swap-quote
                                 :request-hash (hash request)
                                 :chain-id (:chain-id request)))}
             (first (:effects quoted)))
        mismatched (runtime/run-effect
                    {:clock-fn (constantly 1782560000401)
                     :quote-fn (fn [request]
                                 (assoc swap-quote
                                        :amount-in "999"
                                        :request-hash (hash request)
                                        :chain-id (:chain-id request)))}
                    (first (:effects quoted)))
        invalid-clock (try
                        (runtime/run-effect
                         {:clock-fn (constantly "1782560000402")
                          :quote-fn (fn [request]
                                      (assoc swap-quote
                                             :request-hash (hash request)
                                             :chain-id (:chain-id request)))}
                         (first (:effects quoted)))
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        applied (runtime/apply-commands (:state quoted) (:commands ran))]
    (is (= :wallet/quote-swap (get-in quoted [:effects 0 :effect])))
    (is (= 8453 (get-in quoted [:effects 0 :request :chain-id])))
    (is (= "acct:main" (get-in quoted [:effects 0 :request :account-id])))
    (is (= :test-quote (get-in ran [:result :provider])))
    (is (= 8453 (get-in ran [:result :chain-id])))
    (is (= "999" (get-in mismatched [:commands 0 1 :amount-in])))
    (is (= "999" (get-in mismatched [:result :amount-in])))
    (is (= (:request-hash (get-in mismatched [:commands 0 1]))
           (:request-hash (:result mismatched))))
    (is (= :wallet.clock/observed-at (:kind invalid-clock)))
    (is (= :observed-at (:field invalid-clock)))
    (is (= "1782560000402" (:actual invalid-clock)))
    (is (= 1 (count (get-in applied [:state :quotes]))))
    (is (some #(= ":wallet.quote/provider" (:a %)) (:datoms applied)))
    (is (some #(= ":wallet.quote/request-hash" (:a %)) (:datoms applied)))))

(deftest runtime-rejects-host-swap-quotes-with-missing-provenance
  (let [quoted (provider/request (ready-state) "https://app.example"
                                 {:method "wallet_quoteSwap"
                                  :params [swap-request]})
        error (try
                (runtime/run-effect
                 {:quote-fn (fn [_] (dissoc swap-quote :calldata :min-amount-out))}
                 (first (:effects quoted)))
                (catch clojure.lang.ExceptionInfo e
                  (ex-data e)))]
    (is (= :wallet.quote/missing-fields (:kind error)))
    (is (= [:calldata :min-amount-out] (:missing error)))))

(deftest approve-intent-runs-through-host-sign-submit-contract
  (let [prepared (actor/step (ready-state)
                             [:wallet/prepare-contract-call
                              {:id "intent:call:2"
                               :to "0xdef0000000000000000000000000000000000000"
                               :value "0"
                               :data "0x"
                               :origin "https://app.example"}])
        approved (actor/step (:state prepared) [:wallet/approve-intent {:id "intent:call:2"}])
        effect (first (:effects approved))
        env {:clock-fn (constantly 1782560000200)
             :sign-fn (fn [intent]
                        {:raw "0xsigned"
                         :nonce 7
                         :intent-hash (:hash intent)})
             :submit-raw-tx-fn (fn [signed]
                                 {:hash "0xtxhash"
                                  :raw (:raw signed)})}
        ran (runtime/run-effect env effect)
        applied (runtime/apply-commands (:state approved) (:commands ran))]
    (is (= :wallet/sign-and-submit (:effect effect)))
    (is (= "0xtxhash" (get-in applied [:state :txs "0xtxhash" :hash])))
    (is (= :intent.status/submitted
           (get-in applied [:state :intents "intent:call:2" :status])))
    (is (some #(= ":wallet.tx/submitted-at" (:a %)) (:datoms applied)))
    (is (some #(= ":wallet.tx/signed-raw" (:a %)) (:datoms applied)))
    (is (some #(and (= ":wallet.intent/status" (:a %))
                    (= ":intent.status/submitted" (:v_edn %)))
              (:datoms applied)))))

(deftest runtime-rejects-signer-results-for-a-different-approved-payload
  (let [tx-prepared (actor/step (ready-state)
                                [:wallet/prepare-contract-call
                                 {:id "intent:signer-mismatch"
                                  :to "0xdef0000000000000000000000000000000000000"
                                  :value "0"
                                  :data "0x"
                                  :origin "https://app.example"}])
        tx-approved (actor/step (:state tx-prepared)
                                [:wallet/approve-intent {:id "intent:signer-mismatch"}])
        tx-error (try
                   (runtime/run-effect
                    {:sign-fn (fn [_] {:raw "0xwrong" :intent-hash "wallet-intent:v1:wrong"})
                     :submit-raw-tx-fn (fn [_] {:hash "0xshould-not-submit"})}
                    (first (:effects tx-approved)))
                   (catch clojure.lang.ExceptionInfo e
                     (ex-data e)))
        sign-invalid-raw (try
                           (runtime/run-effect
                            {:sign-fn (fn [intent] {:raw "signed"
                                                    :intent-hash (:hash intent)})
                             :submit-raw-tx-fn (fn [_] {:hash "0xshould-not-submit"})}
                            (first (:effects tx-approved)))
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))
        sign-malformed (try
                         (runtime/run-effect
                          {:sign-fn (fn [_] "not-signed")
                           :submit-raw-tx-fn (fn [_] {:hash "0xshould-not-submit"})}
                          (first (:effects tx-approved)))
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        submit-error (try
                       (runtime/run-effect
                        {:sign-fn (fn [intent] {:raw "0xsigned-ok"
                                                :intent-hash (:hash intent)})
                         :submit-raw-tx-fn (fn [_] {:hash "0xsubmitted"
                                                    :raw "0xdifferent-raw"})}
                        (first (:effects tx-approved)))
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))
        submit-missing-hash (try
                              (runtime/run-effect
                               {:sign-fn (fn [intent] {:raw "0xsigned-no-hash"
                                                       :intent-hash (:hash intent)})
                                :submit-raw-tx-fn (fn [signed] {:raw (:raw signed)})}
                               (first (:effects tx-approved)))
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        submit-invalid-hash (try
                              (runtime/run-effect
                               {:sign-fn (fn [intent] {:raw "0xsigned-bad-hash"
                                                       :intent-hash (:hash intent)})
                                :submit-raw-tx-fn (fn [signed] {:hash "submitted"
                                                                :raw (:raw signed)})}
                               (first (:effects tx-approved)))
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        tx-malformed-clock-fn (try
                                (runtime/run-effect
                                 {:clock-fn "not-a-function"
                                  :sign-fn (fn [intent] {:raw "0xsigned-bad-clock-fn"
                                                         :intent-hash (:hash intent)})
                                  :submit-raw-tx-fn (fn [signed] {:hash "0xsubmittedbadclockfn"
                                                                  :raw (:raw signed)})}
                                 (first (:effects tx-approved)))
                                (catch clojure.lang.ExceptionInfo e
                                  (ex-data e)))
        tx-invalid-clock (try
                           (runtime/run-effect
                            {:clock-fn (constantly "1782560000200")
                             :sign-fn (fn [intent] {:raw "0xsigned-bad-clock"
                                                    :intent-hash (:hash intent)})
                             :submit-raw-tx-fn (fn [signed] {:hash "0xsubmittedbadclock"
                                                             :raw (:raw signed)})}
                            (first (:effects tx-approved)))
                           (catch clojure.lang.ExceptionInfo e
                             (ex-data e)))
        msg-prepared (provider/request (ready-state) "https://app.example"
                                       {:method "personal_sign"
                                        :params ["0x68656c6c6f" (:address account)]})
        msg-approved (actor/step (:state msg-prepared)
                                 [:wallet/approve-intent {:id (:result msg-prepared)}])
        msg-error (try
                    (runtime/run-effect
                     {:sign-message-fn (fn [_] {:signature "0xwrong"
                                                :payload-hash "payload:wrong"})}
                     (first (:effects msg-approved)))
                    (catch clojure.lang.ExceptionInfo e
                      (ex-data e)))
        msg-missing-signature (try
                                (runtime/run-effect
                                 {:sign-message-fn (fn [intent]
                                                     {:payload-hash (:payload-hash intent)})}
                                 (first (:effects msg-approved)))
                                (catch clojure.lang.ExceptionInfo e
                                  (ex-data e)))
        msg-invalid-signature (try
                                (runtime/run-effect
                                 {:sign-message-fn (fn [intent]
                                                     {:payload-hash (:payload-hash intent)
                                                      :signature "sig"})}
                                 (first (:effects msg-approved)))
                                (catch clojure.lang.ExceptionInfo e
                                  (ex-data e)))
        msg-invalid-clock (try
                            (runtime/run-effect
                             {:clock-fn (constantly 0)
                              :sign-message-fn (fn [intent]
                                                 {:payload-hash (:payload-hash intent)
                                                  :signature "0xsig"})}
                             (first (:effects msg-approved)))
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))]
    (is (= :wallet.sign/intent-hash (:kind tx-error)))
    (is (= (:hash (get-in tx-approved [:effects 0 :intent])) (:expected tx-error)))
    (is (= "wallet-intent:v1:wrong" (:actual tx-error)))
    (is (= :wallet.sign/raw (:kind sign-invalid-raw)))
    (is (= :raw (:field sign-invalid-raw)))
    (is (= "signed" (:actual sign-invalid-raw)))
    (is (= :wallet.sign/malformed (:kind sign-malformed)))
    (is (= "not-signed" (:actual sign-malformed)))
    (is (= :wallet.submit/signed-raw (:kind submit-error)))
    (is (= "0xsigned-ok" (:expected submit-error)))
    (is (= "0xdifferent-raw" (:actual submit-error)))
    (is (= :wallet.submit/hash (:kind submit-missing-hash)))
    (is (= :hash (:field submit-missing-hash)))
    (is (= :wallet.submit/hash (:kind submit-invalid-hash)))
    (is (= "submitted" (:actual submit-invalid-hash)))
    (is (= :wallet.capability/malformed (:kind tx-malformed-clock-fn)))
    (is (= :clock-fn (:capability tx-malformed-clock-fn)))
    (is (= "not-a-function" (:actual tx-malformed-clock-fn)))
    (is (= :wallet.clock/submitted-at (:kind tx-invalid-clock)))
    (is (= :submitted-at (:field tx-invalid-clock)))
    (is (= "1782560000200" (:actual tx-invalid-clock)))
    (is (= :wallet.sign/payload-hash (:kind msg-error)))
    (is (= (get-in msg-approved [:effects 0 :intent :payload-hash]) (:expected msg-error)))
    (is (= "payload:wrong" (:actual msg-error)))
    (is (= :wallet.sign/signature (:kind msg-missing-signature)))
    (is (= :signature (:field msg-missing-signature)))
    (is (= :wallet.sign/signature (:kind msg-invalid-signature)))
    (is (= "sig" (:actual msg-invalid-signature)))
    (is (= :wallet.clock/signed-at (:kind msg-invalid-clock)))
    (is (= :signed-at (:field msg-invalid-clock)))
    (is (= 0 (:actual msg-invalid-clock)))))

(deftest high-risk-intent-approval-requires-explicit-acknowledgement
  (let [unknown-spender-quote (assoc swap-quote
                                     :router "0xunknownrouter"
                                     :spender "0xunknownrouter")
        prepared (actor/step (ready-state)
                             [:wallet/prepare-swap
                              {:id "swap:high-risk-ack"
                               :origin "https://app.example"
                               :request swap-request
                               :quote unknown-spender-quote}])
        intent-id "swap:high-risk-ack:1"
        without-ack (try
                      (actor/step (:state prepared)
                                  [:wallet/approve-intent {:id intent-id}])
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        with-ack (actor/step (:state prepared)
                             [:wallet/approve-intent {:id intent-id
                                                      :risk-acknowledged? true}])]
    (is (= :risk.level/high (get-in prepared [:state :intents intent-id :risk])))
    (is (= :risk-acknowledged? (:required without-ack)))
    (is (= :risk.level/high (:risk without-ack)))
    (is (= :wallet/sign-and-submit (get-in with-ack [:effects 0 :effect])))
    (is (= :intent.status/approved
           (get-in with-ack [:state :intents intent-id :status])))
    (is (true? (get-in with-ack [:state :intents intent-id :risk-acknowledged?])))
    (is (some #(and (= ":wallet.intent/status" (:a %))
                    (= ":intent.status/approved" (:v_edn %)))
              (:datoms with-ack)))
    (is (some #(and (= ":wallet.intent/risk-acknowledged" (:a %))
                    (= "true" (:v_edn %)))
              (:datoms with-ack)))))

(deftest fatal-swap-risks-cannot-be-approved-even-with-acknowledgement
  (let [expired (actor/step (ready-state)
                            [:wallet/prepare-swap
                             {:id "swap:fatal-expired"
                              :origin "https://app.example"
                              :now-ms 1782560400000
                              :request swap-request
                              :quote swap-quote}])
        expired-error (try
                        (actor/step (:state expired)
                                    [:wallet/approve-intent {:id "swap:fatal-expired:1"
                                                             :risk-acknowledged? true}])
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        mismatched (actor/step (ready-state)
                               [:wallet/prepare-swap
                                {:id "swap:fatal-mismatch"
                                 :origin "https://app.example"
                                 :request swap-request
                                 :quote (assoc swap-quote :from-token "0xdai")}])
        mismatch-error (try
                         (actor/step (:state mismatched)
                                     [:wallet/approve-intent {:id "swap:fatal-mismatch:1"
                                                              :risk-acknowledged? true}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))]
    (is (= :wallet.intent/fatal-risk (:kind expired-error)))
    (is (= [:risk/quote-expired] (:risks expired-error)))
    (is (= 1782560300000
           (get-in expired [:state :intents "swap:fatal-expired:1" :deadline-ms])))
    (is (= 1782560400000
           (get-in expired [:state :intents "swap:fatal-expired:1" :now-ms])))
    (is (re-find #"deadline-ms=1782560300000"
                 (get-in expired [:state :intents "swap:fatal-expired:1" :hash])))
    (is (re-find #"now-ms=1782560400000"
                 (get-in expired [:state :intents "swap:fatal-expired:1" :hash])))
    (is (some #(and (= ":wallet.intent/deadline-ms" (:a %))
                    (= "1782560300000" (:v_edn %)))
              (:datoms expired)))
    (is (some #(and (= ":wallet.intent/now-ms" (:a %))
                    (= "1782560400000" (:v_edn %)))
              (:datoms expired)))
    (is (= :intent.status/pending-user
           (get-in expired [:state :intents "swap:fatal-expired:1" :status])))
    (is (= :wallet.intent/fatal-risk (:kind mismatch-error)))
    (is (= [:risk/quote-request-mismatch] (:risks mismatch-error)))
    (is (= [:from-token]
           (get-in mismatched [:state :intents "swap:fatal-mismatch:1" :quote-mismatch-fields])))
    (is (re-find #"quote-mismatch-fields=\[:from-token\]"
                 (get-in mismatched [:state :intents "swap:fatal-mismatch:1" :hash])))
    (is (some #(and (= ":wallet.intent/quote-mismatch-fields" (:a %))
                    (= "\"[:from-token]\"" (:v_edn %)))
              (:datoms mismatched)))
    (is (= :intent.status/pending-user
           (get-in mismatched [:state :intents "swap:fatal-mismatch:1" :status])))))

(deftest intent-approval-requires-existing-pending-intent
  (let [prepared (actor/step (ready-state)
                             [:wallet/prepare-contract-call
                              {:id "intent:lifecycle:1"
                               :to "0xdef0000000000000000000000000000000000000"
                               :value "0"
                               :data "0x"
                               :origin "https://app.example"}])
        rejected (actor/step (:state prepared)
                             [:wallet/reject-intent {:id "intent:lifecycle:1"
                                                     :reason "user declined"}])
        submitted-state (assoc-in (:state prepared)
                                  [:intents "intent:lifecycle:1" :status]
                                  :intent.status/submitted)
        missing-error (try
                        (actor/step (ready-state)
                                    [:wallet/approve-intent {:id "intent:missing"}])
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        rejected-error (try
                         (actor/step (:state rejected)
                                     [:wallet/approve-intent {:id "intent:lifecycle:1"}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        submitted-error (try
                          (actor/step submitted-state
                                      [:wallet/approve-intent {:id "intent:lifecycle:1"}])
                          (catch clojure.lang.ExceptionInfo e
                            (ex-data e)))]
    (is (= :intent.status/rejected
           (get-in rejected [:state :intents "intent:lifecycle:1" :status])))
    (is (= "user declined"
           (get-in rejected [:state :intents "intent:lifecycle:1" :rejection-reason])))
    (is (some #(and (= ":wallet.intent/status" (:a %))
                    (= ":intent.status/rejected" (:v_edn %)))
              (:datoms rejected)))
    (is (some #(and (= ":wallet.intent/rejection-reason" (:a %))
                    (= "\"user declined\"" (:v_edn %)))
              (:datoms rejected)))
    (is (= "intent:missing" (:id missing-error)))
    (is (= :intent.status/rejected (:status rejected-error)))
    (is (= :intent.status/submitted (:status submitted-error)))))

(deftest tx-confirmation-updates-intent-and-tx-facts
  (let [state (assoc-in (ready-state) [:intents "intent:call:3"]
                        {:id "intent:call:3" :status :intent.status/submitted})
        result (actor/step state [:wallet/tx-confirmed
                                  {:hash "0xtxhash3"
                                   :intent-id "intent:call:3"
                                   :confirmed-at 1782560000300
                                   :block-number 23000001
                                   :gas-used "21000"}])]
    (is (= :intent.status/confirmed
           (get-in result [:state :intents "intent:call:3" :status])))
    (is (some #(= ":wallet.tx/block-number" (:a %)) (:datoms result)))
    (is (some #(= ":wallet.tx/gas-used" (:a %)) (:datoms result)))
    (is (some #(and (= ":wallet.intent/status" (:a %))
                    (= ":intent.status/confirmed" (:v_edn %)))
              (:datoms result)))))

(deftest host-observations-require-valid-intent-status
  (let [base (ready-state)
        missing-tx (try
                     (actor/step base [:wallet/tx-submitted
                                       {:hash "0xmissing"
                                        :intent-id "intent:missing"}])
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))
        pending-state (assoc-in base [:intents "intent:pending"]
                                {:id "intent:pending"
                                 :status :intent.status/pending-user})
        pending-submit (try
                         (actor/step pending-state [:wallet/tx-submitted
                                                    {:hash "0xpending"
                                                     :intent-id "intent:pending"}])
                         (catch clojure.lang.ExceptionInfo e
                           (ex-data e)))
        submitted-state (assoc-in base [:intents "intent:submitted"]
                                  {:id "intent:submitted"
                                   :status :intent.status/submitted})
        missing-confirmed-block (try
                                  (actor/step submitted-state [:wallet/tx-confirmed
                                                               {:hash "0xconfirmed"
                                                                :intent-id "intent:submitted"}])
                                  (catch clojure.lang.ExceptionInfo e
                                    (ex-data e)))
        string-confirmed-block (try
                                 (actor/step submitted-state [:wallet/tx-confirmed
                                                              {:hash "0xconfirmedstring"
                                                               :intent-id "intent:submitted"
                                                               :block-number "23000003"}])
                                 (catch clojure.lang.ExceptionInfo e
                                   (ex-data e)))
        zero-confirmed-block (try
                               (actor/step submitted-state [:wallet/tx-confirmed
                                                            {:hash "0xconfirmedzero"
                                                             :intent-id "intent:submitted"
                                                             :block-number 0}])
                               (catch clojure.lang.ExceptionInfo e
                                 (ex-data e)))
        negative-gas-used (try
                            (actor/step submitted-state [:wallet/tx-confirmed
                                                         {:hash "0xnegativegas"
                                                          :intent-id "intent:submitted"
                                                          :block-number 23000003
                                                          :gas-used "-1"}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        non-decimal-gas-used (try
                               (actor/step submitted-state [:wallet/tx-confirmed
                                                            {:hash "0xbadgas"
                                                             :intent-id "intent:submitted"
                                                             :block-number 23000003
                                                             :gas-used "0x5208"}])
                               (catch clojure.lang.ExceptionInfo e
                                 (ex-data e)))
        too-large-gas-used (try
                             (actor/step submitted-state [:wallet/tx-confirmed
                                                          {:hash "0xhugegas"
                                                           :intent-id "intent:submitted"
                                                           :block-number 23000003
                                                           :gas-used (str swap/max-uint256 "0")}])
                             (catch clojure.lang.ExceptionInfo e
                               (ex-data e)))
        string-confirmed-at (try
                              (actor/step submitted-state [:wallet/tx-confirmed
                                                           {:hash "0xbadconfirmedat"
                                                            :intent-id "intent:submitted"
                                                            :block-number 23000003
                                                            :confirmed-at "1782560000300"}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        zero-confirmed-at (try
                            (actor/step submitted-state [:wallet/tx-confirmed
                                                         {:hash "0xzeroconfirmedat"
                                                          :intent-id "intent:submitted"
                                                          :block-number 23000003
                                                          :confirmed-at 0}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        approved-state (assoc-in base [:intents "intent:approved"]
                                 {:id "intent:approved"
                                  :status :intent.status/approved
                                  :payload-hash "payload:approved"})
        missing-hash (try
                       (actor/step approved-state [:wallet/tx-submitted
                                                   {:intent-id "intent:approved"}])
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))
        invalid-hash (try
                       (actor/step approved-state [:wallet/tx-submitted
                                                   {:hash "submitted"
                                                    :intent-id "intent:approved"
                                                    :submitted-at 1782560000200}])
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))
        missing-submitted-at (try
                               (actor/step approved-state [:wallet/tx-submitted
                                                           {:hash "0xsubmitted"
                                                            :intent-id "intent:approved"}])
                               (catch clojure.lang.ExceptionInfo e
                                 (ex-data e)))
        string-submitted-at (try
                              (actor/step approved-state [:wallet/tx-submitted
                                                          {:hash "0xsubmittedstring"
                                                           :intent-id "intent:approved"
                                                           :submitted-at "1782560000200"}])
                              (catch clojure.lang.ExceptionInfo e
                                (ex-data e)))
        zero-submitted-at (try
                            (actor/step approved-state [:wallet/tx-submitted
                                                        {:hash "0xsubmittedzero"
                                                         :intent-id "intent:approved"
                                                         :submitted-at 0}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        missing-signed-raw (try
                             (actor/step approved-state [:wallet/tx-signed
                                                         {:hash "0xsigned"
                                                          :intent-id "intent:approved"}])
                             (catch clojure.lang.ExceptionInfo e
                               (ex-data e)))
        invalid-signed-raw (try
                             (actor/step approved-state [:wallet/tx-signed
                                                         {:hash "0xsigned"
                                                          :intent-id "intent:approved"
                                                          :signed-raw "signed"}])
                             (catch clojure.lang.ExceptionInfo e
                               (ex-data e)))
        premature-confirm (try
                            (actor/step approved-state [:wallet/tx-confirmed
                                                        {:hash "0xearly"
                                                         :intent-id "intent:approved"
                                                         :block-number 23000003}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        missing-signature (try
                            (actor/step approved-state [:wallet/message-signed
                                                        {:id "sig:missing"
                                                         :intent-id "intent:approved"
                                                         :payload-hash "payload:approved"}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        invalid-signature (try
                            (actor/step approved-state [:wallet/message-signed
                                                        {:id "sig:invalid"
                                                         :intent-id "intent:approved"
                                                         :payload-hash "payload:approved"
                                                         :signature "sig"}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))
        missing-signature-payload-hash (try
                                         (actor/step approved-state [:wallet/message-signed
                                                                     {:id "sig:missing-payload-hash"
                                                                      :intent-id "intent:approved"
                                                                      :signature "0xsig"}])
                                         (catch clojure.lang.ExceptionInfo e
                                           (ex-data e)))
        mismatched-signature-payload-hash (try
                                            (actor/step approved-state [:wallet/message-signed
                                                                        {:id "sig:mismatch"
                                                                         :intent-id "intent:approved"
                                                                         :payload-hash "payload:wrong"
                                                                         :signature "0xsig"}])
                                            (catch clojure.lang.ExceptionInfo e
                                              (ex-data e)))
        invalid-signature-signed-at (try
                                      (actor/step approved-state [:wallet/message-signed
                                                                  {:id "sig:bad-signed-at"
                                                                   :intent-id "intent:approved"
                                                                   :payload-hash "payload:approved"
                                                                   :signature "0xsig"
                                                                   :signed-at "1782560000200"}])
                                      (catch clojure.lang.ExceptionInfo e
                                        (ex-data e)))
        pending-signature (try
                            (actor/step pending-state [:wallet/message-signed
                                                       {:id "sig:pending"
                                                        :intent-id "intent:pending"
                                                        :payload-hash "payload:pending"
                                                        :signature "0xsig"}])
                            (catch clojure.lang.ExceptionInfo e
                              (ex-data e)))]
    (is (= "intent:missing" (:id missing-tx)))
    (is (= :tx/submitted (:observation missing-tx)))
    (is (= :intent.status/pending-user (:status pending-submit)))
    (is (= #{:intent.status/approved} (:allowed-statuses pending-submit)))
    (is (= :hash (:field missing-hash)))
    (is (= :tx/submitted (:observation missing-hash)))
    (is (= :hash (:field invalid-hash)))
    (is (= "submitted" (:actual invalid-hash)))
    (is (= :submitted-at (:field missing-submitted-at)))
    (is (= :tx/submitted (:observation missing-submitted-at)))
    (is (= :submitted-at (:field string-submitted-at)))
    (is (= "1782560000200" (:actual string-submitted-at)))
    (is (= :submitted-at (:field zero-submitted-at)))
    (is (= 0 (:actual zero-submitted-at)))
    (is (= :signed-raw (:field missing-signed-raw)))
    (is (= :tx/signed (:observation missing-signed-raw)))
    (is (= :signed-raw (:field invalid-signed-raw)))
    (is (= "signed" (:actual invalid-signed-raw)))
    (is (= :block-number (:field missing-confirmed-block)))
    (is (= :tx/confirmed (:observation missing-confirmed-block)))
    (is (= :block-number (:field string-confirmed-block)))
    (is (= "23000003" (:actual string-confirmed-block)))
    (is (= :block-number (:field zero-confirmed-block)))
    (is (= 0 (:actual zero-confirmed-block)))
    (is (= :gas-used (:field negative-gas-used)))
    (is (= "-1" (:actual negative-gas-used)))
    (is (= :gas-used (:field non-decimal-gas-used)))
    (is (= "0x5208" (:actual non-decimal-gas-used)))
    (is (= :gas-used (:field too-large-gas-used)))
    (is (= :confirmed-at (:field string-confirmed-at)))
    (is (= "1782560000300" (:actual string-confirmed-at)))
    (is (= :confirmed-at (:field zero-confirmed-at)))
    (is (= 0 (:actual zero-confirmed-at)))
    (is (= :signature (:field missing-signature)))
    (is (= :message/signed (:observation missing-signature)))
    (is (= :signature (:field invalid-signature)))
    (is (= "sig" (:actual invalid-signature)))
    (is (= :payload-hash (:field missing-signature-payload-hash)))
    (is (= :message/signed (:observation missing-signature-payload-hash)))
    (is (= :wallet.signature/payload-hash (:kind mismatched-signature-payload-hash)))
    (is (= "payload:approved" (:expected mismatched-signature-payload-hash)))
    (is (= "payload:wrong" (:actual mismatched-signature-payload-hash)))
    (is (= :signed-at (:field invalid-signature-signed-at)))
    (is (= "1782560000200" (:actual invalid-signature-signed-at)))
    (is (= :intent.status/approved (:status premature-confirm)))
    (is (= #{:intent.status/submitted} (:allowed-statuses premature-confirm)))
    (is (= :message/signed (:observation pending-signature)))
    (is (= :intent.status/pending-user (:status pending-signature)))))

(deftest runtime-sync-materializes-chain-observations
  (let [state (assoc-in (ready-state) [:intents "intent:sync:1"]
                        {:id "intent:sync:1" :status :intent.status/submitted})
        sync-effect (first (:effects (actor/step state [:wallet/sync {:chain-id 1
                                                                       :account-id "acct:main"}])))
        ran (runtime/run-effect
             {:sync-fn (fn [request]
                         {:result {:synced-chain-id (:chain-id request)}
                          :balances [{:account-id "acct:main"
                                      :chain-id 1
                                      :asset "native"
                                      :block-number 23000002
                                      :raw "42"
                                      :observed-at 1782560000500}]
                          :allowances [{:account-id "acct:main"
                                        :chain-id 1
                                        :token "0xusdc"
                                        :spender "0xrouter"
                                        :amount "0"
                                        :block-number 23000002
                                        :observed-at 1782560000500}]
                          :receipts [{:hash "0xtxsync"
                                      :intent-id "intent:sync:1"
                                      :confirmed-at 1782560000600
                                      :block-number 23000002
                                      :gas-used "31000"}]})}
             sync-effect)
        applied (runtime/apply-commands state (:commands ran))]
    (is (= [[:wallet/observe-balance {:account-id "acct:main"
                                      :chain-id 1
                                      :asset "native"
                                      :block-number 23000002
                                      :raw "42"
                                      :observed-at 1782560000500}]
            [:wallet/observe-allowance {:account-id "acct:main"
                                        :chain-id 1
                                        :token "0xusdc"
                                        :spender "0xrouter"
                                        :amount "0"
                                        :block-number 23000002
                                        :observed-at 1782560000500}]
            [:wallet/tx-confirmed {:hash "0xtxsync"
                                   :intent-id "intent:sync:1"
                                   :confirmed-at 1782560000600
                                   :block-number 23000002
                                   :gas-used "31000"}]]
           (:commands ran)))
    (is (= "42" (get-in applied [:state :balances ["acct:main" 1 "native"] :raw])))
    (is (= "0" (get-in applied [:state :allowances ["acct:main" 1 "0xusdc" "0xrouter"]])))
    (is (= :intent.status/confirmed
           (get-in applied [:state :intents "intent:sync:1" :status])))
    (is (some #(= ":wallet.balance/raw" (:a %)) (:datoms applied)))
    (is (some #(= ":wallet.allowance/amount" (:a %)) (:datoms applied)))
    (is (some #(= ":wallet.tx/gas-used" (:a %)) (:datoms applied)))))

(deftest runtime-sync-preserves-explicit-host-commands-before-observations
  (let [state (ready-state)
        sync-effect (first (:effects (actor/step state [:wallet/sync {:chain-id 1
                                                                       :account-id "acct:main"}])))
        ran (runtime/run-effect
             {:sync-fn (fn [_]
                         {:result {:source :host}
                          :commands [[:wallet/observe-balance {:account-id "acct:main"
                                                               :chain-id 1
                                                               :asset "native"
                                                               :block-number 23000004
                                                               :raw "1"
                                                               :observed-at 1782560000800}]]
                          :balances [{:account-id "acct:main"
                                      :chain-id 1
                                      :asset "native"
                                      :block-number 23000005
                                      :raw "2"
                                      :observed-at 1782560000801}]})}
             sync-effect)
        applied (runtime/apply-commands state (:commands ran))]
    (is (= [:wallet/observe-balance :wallet/observe-balance]
           (mapv first (:commands ran))))
    (is (= "1" (get-in ran [:commands 0 1 :raw])))
    (is (= "2" (get-in ran [:commands 1 1 :raw])))
    (is (= "2"
           (get-in applied [:state :balances ["acct:main" 1 "native"] :raw])))))

(deftest actor-replay-validates-sync-command-before-effect
  (let [missing-chain (try
                        (actor/step (ready-state) [:wallet/sync {:account-id "acct:main"}])
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        bad-chain (try
                    (actor/step (ready-state) [:wallet/sync {:chain-id 0
                                                             :account-id "acct:main"}])
                    (catch clojure.lang.ExceptionInfo e
                      (ex-data e)))
        bad-account (try
                      (actor/step (ready-state) [:wallet/sync {:chain-id 1
                                                               :account-id ""}])
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))
        bad-origin (try
                     (actor/step (ready-state) [:wallet/sync {:chain-id 1
                                                              :origin ""}])
                     (catch clojure.lang.ExceptionInfo e
                       (ex-data e)))]
    (is (= :wallet.sync/missing-fields (:kind missing-chain)))
    (is (= [:chain-id] (:missing missing-chain)))
    (is (= :wallet.sync/chain-id (:kind bad-chain)))
    (is (= 0 (:actual bad-chain)))
    (is (= :wallet.sync/account-id (:kind bad-account)))
    (is (= "" (:actual bad-account)))
    (is (= :wallet.sync/origin (:kind bad-origin)))
    (is (= "" (:actual bad-origin)))))

(deftest runtime-command-replay-rejects-invalid-batch-without-caller-state-mutation
  (let [state (ready-state)
        commands [[:wallet/observe-balance {:account-id "acct:main"
                                            :chain-id 1
                                            :asset "native"
                                            :block-number 23000003
                                            :raw "99"
                                            :observed-at 1782560000700}]
                  [:wallet/tx-confirmed {:hash "0xmissingintent"
                                         :intent-id "intent:missing"
                                         :block-number 23000003}]]
        replay-error (try
                       (runtime/apply-commands state commands)
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))]
    (is (= "intent:missing" (:id replay-error)))
    (is (= :tx/confirmed (:observation replay-error)))
    (is (nil? (get-in state [:balances ["acct:main" 1 "native"]])))
    (is (nil? (get-in state [:txs "0xmissingintent"])))))

(deftest provider-denies-unauthorized-method
  (let [state (assoc-in (ready-state) [:policies "https://limited.example"]
                        {:origin "https://limited.example"
                         :accounts ["acct:main"]
                         :chains [1]
                         :caps #{:eth/accounts}})]
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"not authorized"
                          (provider/request state "https://limited.example"
                                            {:method "eth_sendTransaction"
                                             :params [{}]})))))

(deftest provider-rejects-invalid-request-params-before-intent-creation
  (let [invalid (fn [req]
                  (try
                    (provider/request (ready-state) "https://app.example" req)
                    (catch clojure.lang.ExceptionInfo e
                      (ex-data e))))
        missing-tx (invalid {:method "eth_sendTransaction"
                             :params []})
        empty-tx (invalid {:method "eth_sendTransaction"
                           :params [{}]})
        contract-create (provider/request (ready-state) "https://app.example"
                                          {:method "eth_sendTransaction"
                                           :params [{:from (:address account)
                                                     :data "0x6000"
                                                     :value "0x0"}]})
        missing-transfer (invalid {:method "wallet_prepareTransfer"
                                   :params [{:to "0xdef0000000000000000000000000000000000000"}]})
        bad-watch-address (invalid {:method "wallet_watchAsset"
                                    :params [{:type "ERC20"
                                              :options {:address "0xUSDC"
                                                        :symbol "USDC"
                                                        :decimals 6}}]})
        bad-watch-type (invalid {:method "wallet_watchAsset"
                                 :params [{:type "ERC777"
                                           :options {:address "0x0000000000000000000000000000000000000abc"
                                                     :symbol "TOK"
                                                     :decimals 18}}]})
        bad-watch-decimals (invalid {:method "wallet_watchAsset"
                                     :params [{:type "ERC20"
                                               :options {:address "0x0000000000000000000000000000000000000abc"
                                                         :symbol "USDC"
                                                         :decimals "6"}}]})
        missing-revoke (invalid {:method "wallet_revokeApproval"
                                 :params [{:token "0xusdc"}]})
        missing-quote (invalid {:method "wallet_quoteSwap"
                                :params [(dissoc swap-request :amount-in)]})
        missing-prepare-swap (invalid {:method "wallet_prepareSwap"
                                       :params [{:quote swap-quote}]})
        missing-sign (invalid {:method "personal_sign"
                               :params ["0x68656c6c6f"]})
        bad-chain (invalid {:method "wallet_switchEthereumChain"
                            :params [{:chainId "not-a-chain"}]})]
    (is (every? #(= -32602 (:code %))
                [missing-tx missing-transfer missing-revoke missing-quote
                 missing-prepare-swap missing-sign bad-chain empty-tx
                 bad-watch-address bad-watch-type bad-watch-decimals]))
    (is (every? #(= :invalid-params (:error-kind %))
                [missing-tx missing-transfer missing-revoke missing-quote
                 missing-prepare-swap missing-sign bad-chain empty-tx
                 bad-watch-address bad-watch-type bad-watch-decimals]))
    (is (= :first-param-must-be-map (:reason missing-tx)))
    (is (= :missing-one-of-fields (:reason empty-tx)))
    (is (= [:to :data] (:fields empty-tx)))
    (is (= :evm/simulate (get-in contract-create [:effects 0 :effect])))
    (is (= [:amount] (:missing missing-transfer)))
    (is (= :invalid-asset-address (:reason bad-watch-address)))
    (is (= :unsupported-asset-type (:reason bad-watch-type)))
    (is (= :invalid-asset-decimals (:reason bad-watch-decimals)))
    (is (= [:spender] (:missing missing-revoke)))
    (is (= [:amount-in] (:missing missing-quote)))
    (is (= [:from-token :to-token :amount-in] (:missing missing-prepare-swap)))
    (is (= [:address :payload] (:missing missing-sign)))
    (is (= :invalid-chain-id (:reason bad-chain)))))

(deftest provider-errors-carry-eip1193-codes
  (let [limited (assoc-in (ready-state) [:policies "https://limited.example"]
                          {:origin "https://limited.example"
                           :accounts ["acct:main"]
                           :chains [1]
                           :caps #{:eth/accounts}})
        unauthorized (try
                       (provider/request limited "https://limited.example"
                                         {:method "eth_sendTransaction"
                                          :params [{}]})
                       (catch clojure.lang.ExceptionInfo e
                         (ex-data e)))
        unknown-chain (try
                        (provider/request (ready-state) "https://app.example"
                                          {:method "wallet_switchEthereumChain"
                                           :params [{:chainId "0x539"}]})
                        (catch clojure.lang.ExceptionInfo e
                          (ex-data e)))
        unsupported (try
                      (provider/request (ready-state) "https://app.example"
                                        {:method "wallet_unimplemented"
                                         :params []})
                      (catch clojure.lang.ExceptionInfo e
                        (ex-data e)))]
    (is (= 4100 (:code unauthorized)))
    (is (= :unauthorized (:error-kind unauthorized)))
    (is (= 4902 (:code unknown-chain)))
    (is (= 1337 (:chain-id unknown-chain)))
    (is (= 4200 (:code unsupported)))
    (is (= :unsupported-method (:error-kind unsupported)))))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.wallet-test)]
    (System/exit (if (zero? (+ fail error)) 0 1))))
