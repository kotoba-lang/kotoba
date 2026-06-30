(ns kotoba.wallet.runtime
  "Host-effect runner contract for wallet effects.

   This namespace is intentionally thin. It composes injected host functions and
   returns actor commands/events that can be committed as wallet facts. It never
   owns key material or ambient network access."
  (:require [clojure.string :as str]
            #?(:cljs [cljs.reader :as reader])
            [kotoba.wallet.actor :as actor]
            [kotoba.wallet.swap :as swap]))

(defn require-fn [env k]
  (let [f (get env k)]
    (cond
      (nil? f)
      (throw (ex-info "missing wallet host capability" {:capability k}))

      (not (fn? f))
      (throw (ex-info "wallet host capability must be a function"
                      {:kind :wallet.capability/malformed
                       :capability k
                       :actual f}))

      :else f)))

(defn ensure-host-match! [expected actual kind]
  (when (and actual (not= expected actual))
    (throw (ex-info "wallet host result does not match approved intent"
                    {:expected expected
                     :actual actual
                     :kind kind}))))

(defn require-field! [m k kind]
  (let [v (get m k)]
    (when (nil? v)
      (throw (ex-info "wallet host result is missing required field"
                      {:field k
                       :kind kind})))
    v))

(defn require-host-map! [m kind]
  (when-not (map? m)
    (throw (ex-info "wallet host result must be an object"
                    {:kind kind
                     :actual m})))
  m)

(defn hex-prefixed? [v]
  (and (string? v)
       (re-matches #"0x.+" v)))

(defn require-hex-field! [m k kind]
  (let [v (require-field! m k kind)]
    (when-not (hex-prefixed? v)
      (throw (ex-info "wallet host result has invalid hex field"
                      {:field k
                       :kind kind
                       :actual v})))
    v))

(defn positive-integer? [v]
  (and (integer? v) (pos? v)))

(defn require-positive-integer! [v field kind]
  (when-not (positive-integer? v)
    (throw (ex-info "wallet host result has invalid timestamp"
                    {:field field
                     :kind kind
                     :actual v})))
  v)

(defn host-clock-value [env clock-key field kind]
  (when (contains? env clock-key)
    (let [clock-fn (require-fn env clock-key)]
      (require-positive-integer! (clock-fn) field kind))))

(defn sync-observations->commands [result]
  (let [commands (:commands result)]
    (vec
     (concat
      (or commands [])
      (map (fn [balance] [:wallet/observe-balance balance]) (:balances result))
      (map (fn [allowance] [:wallet/observe-allowance allowance]) (:allowances result))
      (map (fn [receipt] [:wallet/tx-confirmed receipt]) (:receipts result))))))

(defn run-effect
  "Run one effect description with injected host capabilities.

   Required env keys by effect:
   - :evm/simulate           -> :simulate-fn
   - :wallet/sign-and-submit -> :sign-fn, :submit-raw-tx-fn, optional :clock-fn
   - :wallet/sign-message    -> :sign-message-fn, optional :clock-fn
   - :evm-rpc/call          -> :evm-rpc-fn
   - :evm-rpc/estimate-gas  -> :evm-rpc-fn
   - :wallet/quote-swap     -> :quote-fn
   - :wallet/sync           -> :sync-fn

   Returns a map shaped like {:result ... :commands [...]} where commands can be
   fed back through kotoba.wallet.actor/step."
  [env {:keys [effect] :as e}]
  (case effect
    :evm/simulate
    {:result ((require-fn env :simulate-fn) (:intent e))
     :commands []}

    :wallet/sign-and-submit
    (let [intent (:intent e)
          signed (require-host-map! ((require-fn env :sign-fn) intent)
                                    :wallet.sign/malformed)
          signed-raw (require-hex-field! signed :raw :wallet.sign/raw)
          _ (ensure-host-match! (:hash intent) (:intent-hash signed) :wallet.sign/intent-hash)
          submitted (require-host-map! ((require-fn env :submit-raw-tx-fn) signed)
                                       :wallet.submit/malformed)
          _ (ensure-host-match! signed-raw (:raw submitted) :wallet.submit/signed-raw)
          tx-hash (require-hex-field! submitted :hash :wallet.submit/hash)
          now (host-clock-value env :clock-fn :submitted-at :wallet.clock/submitted-at)
          tx-record {:hash tx-hash
                     :intent-id (:id intent)
                     :nonce (:nonce signed)
                     :signed-raw signed-raw
                     :submitted-at now}]
      {:result submitted
       :commands [[:wallet/tx-signed (assoc tx-record :status :tx.status/signed)]
                  [:wallet/tx-submitted tx-record]]})

    :wallet/sign-message
    (let [intent (:intent e)
          signed (require-host-map! ((require-fn env :sign-message-fn) intent)
                                    :wallet.sign-message/malformed)
          _ (ensure-host-match! (:payload-hash intent) (:payload-hash signed) :wallet.sign/payload-hash)
          signature (require-hex-field! signed :signature :wallet.sign/signature)
          now (host-clock-value env :clock-fn :signed-at :wallet.clock/signed-at)
          signature-record {:id (or (:id signed) (str "sig:" (hash [(:id intent) signature])))
                            :intent-id (:id intent)
                            :account-id (:account-id intent)
                            :chain-id (:chain-id intent)
                            :origin (:origin intent)
                            :kind (:kind intent)
                            :payload-hash (:payload-hash intent)
                            :signature signature
                            :signed-at now}]
      {:result signed
       :commands [[:wallet/message-signed signature-record]]})

    :evm-rpc/call
    {:result ((require-fn env :evm-rpc-fn) {:method "eth_call"
                                            :chain-id (:chain-id e)
                                            :params (:params e)})
     :commands []}

    :evm-rpc/estimate-gas
    {:result ((require-fn env :evm-rpc-fn) {:method "eth_estimateGas"
                                            :chain-id (:chain-id e)
                                            :params (:params e)})
     :commands []}

    :wallet/quote-swap
    (let [quote (require-host-map! ((require-fn env :quote-fn) (:request e))
                                   :wallet.quote/malformed)
          now (host-clock-value env :clock-fn :observed-at :wallet.clock/observed-at)
          quote (merge (:request e)
                       quote
                       {:observed-at now
                        :request-hash (or (:request-hash quote)
                                          (str (hash (:request e))))})
          quote (swap/ensure-observed-quote! quote)]
      {:result quote
       :commands [[:wallet/quote-observed quote]]})

    :wallet/sync
    (let [result ((require-fn env :sync-fn) (:request e))
          result (if (map? result) result {:result result})]
      (assoc result :commands (sync-observations->commands result)))

    (throw (ex-info "unsupported wallet effect" {:effect effect :effect-map e}))))

(defn apply-commands [state commands]
  (reduce (fn [{:keys [state] :as acc} command]
            (let [result (actor/step state command)]
              (-> acc
                  (assoc :state (:state result))
                  (update :events into (:events result))
                  (update :effects into (:effects result))
                  (update :datoms into (:datoms result)))))
          {:state state :events [] :effects [] :datoms []}
          commands))

#?(:cljs
   (do
     (defn- camel->kebab [s]
       (-> s
           (str/replace #"([a-z0-9])([A-Z])" "$1-$2")
           str/lower-case))

     (defn- normalize-js-key [k]
       (if (keyword? k)
         (keyword (camel->kebab (name k)))
         (keyword (camel->kebab (str k)))))

     (defn- maybe-keyword-value [x]
       (if (and (string? x)
                (boolean (re-matches #"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+" x)))
         (keyword x)
         x))

     (defn- normalize-js-value [x]
       (cond
         (map? x)
         (into {}
               (map (fn [[k v]]
                      [(normalize-js-key k) (normalize-js-value v)]))
               x)

         (vector? x)
         (mapv normalize-js-value x)

         (seq? x)
         (mapv normalize-js-value x)

         :else (maybe-keyword-value x)))

     (defn- maybe-keyword [x]
       (if (string? x) (keyword x) x))

     (def eip1193-method->cap
       {"eth_accounts" :eth/accounts
        "eth_requestAccounts" :eth/accounts
        "eth_chainId" :eth/chain-id
        "wallet_switchEthereumChain" :eth/switch-chain
        "wallet_addEthereumChain" :eth/add-chain
        "wallet_watchAsset" :eth/watch-asset
        "eth_call" :eth/call
        "eth_estimateGas" :eth/estimate-gas
        "eth_sendTransaction" :eth/send-tx
        "wallet_prepareTransfer" :eth/prepare-transfer
        "wallet_revokeApproval" :eth/revoke-approval
        "wallet_quoteSwap" :eth/quote-swap
        "wallet_prepareSwap" :eth/prepare-swap
        "personal_sign" :eth/sign-message
        "eth_signTypedData_v4" :eth/sign-typed-data})

     (defn- cap-keyword [cap]
       (cond
         (keyword? cap) cap
         (contains? eip1193-method->cap cap) (get eip1193-method->cap cap)
         (and (string? cap) (str/includes? cap "/"))
         (let [[ns name] (str/split cap #"/" 2)]
           (keyword ns name))
         (string? cap) (keyword "eth" cap)
         :else cap))

     (defn- parse-chain-id [chain-id]
       (try
         (let [parsed (cond
                        (integer? chain-id) chain-id
                        (and (string? chain-id) (re-matches #"0x[0-9a-fA-F]+" chain-id))
                        (js/parseInt (subs chain-id 2) 16)
                        (and (string? chain-id) (re-matches #"[0-9]+" chain-id))
                        (js/parseInt chain-id 10)
                        :else nil)]
           (when (and parsed (pos? parsed) (not (js/isNaN parsed)))
             parsed))
         (catch :default _
           nil)))

     (defn- normalize-chain-id-fields [x]
       (cond
         (map? x)
         (let [m (into {}
                       (map (fn [[k v]]
                              [k (normalize-chain-id-fields v)]))
                       x)]
           (if (contains? m :chain-id)
             (if-let [chain-id (parse-chain-id (:chain-id m))]
               (assoc m :chain-id chain-id)
               m)
             m))

         (vector? x)
         (mapv normalize-chain-id-fields x)

         (seq? x)
         (mapv normalize-chain-id-fields x)

         :else x))

     (defn- normalize-record-map [m field]
       (when (and (some? m)
                  (not (map? m)))
         (throw (ex-info (str "wallet " field " must be an object")
                         {:kind (keyword (str "wallet." field) "malformed")
                          :actual m})))
       (into {}
             (map (fn [[k v]]
                    [(str k) (normalize-js-value v)]))
             (or m {})))

     (defn- normalize-accounts [accounts]
       (when (and (some? accounts)
                  (not (map? accounts)))
         (throw (ex-info "wallet accounts must be an object"
                         {:kind :wallet.accounts/malformed
                          :actual accounts})))
       (into {}
             (map (fn [[k v]]
                    (let [record (normalize-js-value v)
                          id (or (:id record) (str k))]
                      [id (assoc record :id id)])))
             (or accounts {})))

     (defn- lower-address [address]
       (when address (str/lower-case address)))

     (defn- policy-account-id [accounts account-ref]
       (when (some? account-ref)
         (let [account-ref (str account-ref)
               account-ref-lower (str/lower-case account-ref)]
           (or (when (contains? accounts account-ref)
                 account-ref)
               (some (fn [[id account]]
                       (when (= account-ref-lower (lower-address (:address account)))
                         id))
                     accounts)
               account-ref))))

     (defn- normalize-networks [networks]
       (when (and (some? networks)
                  (not (map? networks)))
         (throw (ex-info "wallet networks must be an object"
                         {:kind :wallet.networks/malformed
                          :actual networks})))
       (into {}
             (keep (fn [[k v]]
                     (let [record (normalize-js-value v)
                           chain-id (or (parse-chain-id (:chain-id record))
                                        (parse-chain-id k))]
                       (when chain-id
                         [chain-id (assoc record :chain-id chain-id)]))))
             (or networks {})))

     (defn- normalize-policies [accounts policies]
       (when (and (some? policies)
                  (not (map? policies)))
         (throw (ex-info "wallet policies must be an object"
                         {:kind :wallet.policies/malformed
                          :actual policies})))
       (into {}
             (map (fn [[k v]]
                    (let [record (normalize-js-value v)]
                      [(str k) (-> record
                                   (update :accounts #(mapv (partial policy-account-id accounts) (or % [])))
                                   (update :chains #(vec (keep parse-chain-id (or % []))))
                                   (update :caps #(vec (distinct (map cap-keyword (or % []))))))])))
             (or policies {})))

     (defn- maybe-composite-key [k]
       (if (and (string? k) (str/starts-with? k "["))
         (try
           (let [v (reader/read-string k)]
             (if (vector? v) v k))
           (catch :default _
             k))
         k))

     (defn- normalize-composite-key-map [m field]
       (when (and (some? m)
                  (not (map? m)))
         (throw (ex-info (str "wallet " field " must be an object")
                         {:kind (keyword (str "wallet." field) "malformed")
                          :actual m})))
       (into {}
             (map (fn [[k v]]
                    [(maybe-composite-key (str k)) (normalize-js-value v)]))
             (or m {})))

     (defn- normalize-state-js [state]
       (let [raw (js->clj state)]
         (when-not (map? raw)
           (throw (ex-info "wallet state must be an object"
                           {:kind :wallet.state/malformed
                            :actual raw})))
         (let [accounts (normalize-accounts (get raw "accounts"))
               selected-account-ref (or (get raw "selected-account-id")
                                        (get raw "selectedAccountId"))]
           (-> actor/empty-state
               (merge (normalize-js-value raw))
               (assoc :accounts accounts
                      :networks (normalize-networks (get raw "networks"))
                      :policies (normalize-policies accounts (get raw "policies"))
                      :assets (normalize-composite-key-map (get raw "assets") "assets")
                      :allowances (normalize-composite-key-map (get raw "allowances") "allowances")
                      :balances (normalize-composite-key-map (get raw "balances") "balances")
                      :intents (normalize-record-map (get raw "intents") "intents")
                      :txs (normalize-record-map (get raw "txs") "txs")
                      :quotes (normalize-record-map (get raw "quotes") "quotes")
                      :signatures (normalize-record-map (get raw "signatures") "signatures")
                      :selected-account-id (policy-account-id accounts selected-account-ref)
                      :selected-chain-id (parse-chain-id (or (get raw "selected-chain-id")
                                                             (get raw "selectedChainId"))))))))

     (defn- keyword->js-string [k]
       (if-let [ns (namespace k)]
         (str ns "/" (name k))
         (name k)))

     (defn- wallet-clj->js [x]
       (cond
         (keyword? x)
         (keyword->js-string x)

         (map? x)
         (clj->js (into {}
                       (map (fn [[k v]]
                              [(if (keyword? k) (name k) k)
                               (wallet-clj->js v)]))
                       x))

         (vector? x)
         (clj->js (mapv wallet-clj->js x))

         (seq? x)
         (clj->js (mapv wallet-clj->js x))

         :else x))

     (defn- normalize-effect-js [effect]
       (let [effect (normalize-chain-id-fields
                     (normalize-js-value (js->clj effect :keywordize-keys true)))]
         (when-not (map? effect)
           (throw (ex-info "wallet effect must be an object"
                           {:kind :wallet.effect/malformed
                            :actual effect})))
         (update effect :effect maybe-keyword)))

     (defn- normalize-env-js [env]
       (let [env (js->clj env :keywordize-keys true)]
         (when-not (map? env)
           (throw (ex-info "wallet runtime env must be an object"
                           {:kind :wallet.env/malformed
                            :actual env})))
         env))

     (defn- command-tuple! [command]
       (when-not (and (vector? command) (= 2 (count command)))
         (throw (ex-info "wallet command must be a two-item tuple"
                         {:kind :wallet.command/malformed
                          :actual command})))
       command)

     (defn- normalize-command-js [command]
       (let [[event payload] (command-tuple! command)]
         [(maybe-keyword event) (normalize-chain-id-fields (normalize-js-value payload))]))

     (defn- normalize-commands-js [commands]
       (let [commands (js->clj commands :keywordize-keys true)]
         (when-not (vector? commands)
           (throw (ex-info "wallet commands must be an array"
                           {:kind :wallet.commands/malformed
                            :actual commands})))
         (mapv normalize-command-js commands)))

     (defn- js-host-fn [f]
       (fn [request]
         (normalize-chain-id-fields
          (normalize-js-value (js->clj (f (clj->js request))
                                       :keywordize-keys true)))))

     (defn- promise-like? [x]
       (and (some? x)
            (fn? (.-then x))))

     (defn- normalize-host-result-js [x]
       (normalize-chain-id-fields
        (normalize-js-value (js->clj x :keywordize-keys true))))

     (defn- call-host-js [f request]
       (let [result (f (clj->js request))]
         (if (promise-like? result)
           (.then result normalize-host-result-js)
           (normalize-host-result-js result))))

     (defn- require-js-fn [env js-k capability]
       (let [f (get env js-k)]
         (cond
           (nil? f)
           (throw (ex-info "missing wallet host capability" {:capability capability}))

           (not (fn? f))
           (throw (ex-info "wallet host capability must be a function"
                           {:kind :wallet.capability/malformed
                            :capability capability}))

           :else f)))

     (defn- then-result [x f]
       (if (promise-like? x)
         (.then x f)
         (f x)))

     (defn- maybe-wallet-clj->js [x]
       (if (promise-like? x)
         (.then x wallet-clj->js)
         (wallet-clj->js x)))

     (declare runtime-error-js)

     (defn- maybe-catch-runtime-error [x]
       (if (promise-like? x)
         (.catch x (fn [e] (throw (runtime-error-js e))))
         x))

     (defn- run-effect-js* [env effect]
       (case (:effect effect)
         :evm/simulate
         (then-result (call-host-js (require-js-fn env :simulateFn :simulate-fn) (:intent effect))
                      (fn [result]
                        {:result result :commands []}))

         :wallet/sign-and-submit
         (then-result
          (call-host-js (require-js-fn env :signFn :sign-fn) (:intent effect))
          (fn [signed]
            (let [signed (require-host-map! signed :wallet.sign/malformed)
                  signed-raw (require-hex-field! signed :raw :wallet.sign/raw)]
              (ensure-host-match! (get-in effect [:intent :hash])
                                  (:intent-hash signed)
                                  :wallet.sign/intent-hash)
              (then-result
               (call-host-js (require-js-fn env :submitRawTxFn :submit-raw-tx-fn) signed)
               (fn [submitted]
                 (let [submitted (require-host-map! submitted :wallet.submit/malformed)]
                   (ensure-host-match! signed-raw
                                       (:raw submitted)
                                       :wallet.submit/signed-raw)
                   (let [intent (:intent effect)
                         tx-hash (require-hex-field! submitted :hash :wallet.submit/hash)
                         now (host-clock-value env :clockFn :submitted-at :wallet.clock/submitted-at)
                         tx-record {:hash tx-hash
                                    :intent-id (:id intent)
                                    :nonce (:nonce signed)
                                    :signed-raw signed-raw
                                    :submitted-at now}]
                     {:result submitted
                      :commands [[:wallet/tx-signed (assoc tx-record :status :tx.status/signed)]
                                 [:wallet/tx-submitted tx-record]]})))))))

         :wallet/sign-message
         (then-result
          (call-host-js (require-js-fn env :signMessageFn :sign-message-fn) (:intent effect))
          (fn [signed]
            (let [signed (require-host-map! signed :wallet.sign-message/malformed)
                  intent (:intent effect)
                  _ (ensure-host-match! (:payload-hash intent)
                                        (:payload-hash signed)
                                        :wallet.sign/payload-hash)
                  signature (require-hex-field! signed :signature :wallet.sign/signature)
                  now (host-clock-value env :clockFn :signed-at :wallet.clock/signed-at)
                  signature-record {:id (or (:id signed) (str "sig:" (hash [(:id intent) signature])))
                                    :intent-id (:id intent)
                                    :account-id (:account-id intent)
                                    :chain-id (:chain-id intent)
                                    :origin (:origin intent)
                                    :kind (:kind intent)
                                    :payload-hash (:payload-hash intent)
                                    :signature signature
                                    :signed-at now}]
              {:result signed
               :commands [[:wallet/message-signed signature-record]]})))

         :evm-rpc/call
         (then-result
          (call-host-js (require-js-fn env :evmRpcFn :evm-rpc-fn) {:method "eth_call"
                                                                    :chain-id (:chain-id effect)
                                                                    :params (:params effect)})
          (fn [result]
            {:result result :commands []}))

         :evm-rpc/estimate-gas
         (then-result
          (call-host-js (require-js-fn env :evmRpcFn :evm-rpc-fn) {:method "eth_estimateGas"
                                                                    :chain-id (:chain-id effect)
                                                                    :params (:params effect)})
          (fn [result]
            {:result result :commands []}))

         :wallet/quote-swap
         (then-result
          (call-host-js (require-js-fn env :quoteFn :quote-fn) (:request effect))
          (fn [quote]
            (let [quote (require-host-map! quote :wallet.quote/malformed)
                  now (host-clock-value env :clockFn :observed-at :wallet.clock/observed-at)
                  quote (merge (:request effect)
                               quote
                               {:observed-at now
                                :request-hash (or (:request-hash quote)
                                                  (str (hash (:request effect))))})
                  quote (swap/ensure-observed-quote! quote)]
              {:result quote
               :commands [[:wallet/quote-observed quote]]})))

         :wallet/sync
         (then-result
          (call-host-js (require-js-fn env :syncFn :sync-fn) (:request effect))
          (fn [result]
            (let [result (if (map? result) result {:result result})]
              (assoc result :commands (sync-observations->commands result)))))

         (throw (ex-info "unsupported wallet effect" {:effect (:effect effect)
                                                      :effect-map effect}))))

     (defn- runtime-error-js [e]
       (let [message (or (.-message e) "wallet runtime effect failed")
             data (assoc (or (ex-data e) {})
                         :error-kind :wallet-runtime)
             err (js/Error. message)]
         (set! (.-data err) (wallet-clj->js data))
         err))

     (defn run-effect-js
       "JS-facing host-effect runner. env is converted with keyword keys and may
        contain JS functions under names like simulateFn/signFn/submitRawTxFn.
        Prefer the Clojure `run-effect` from CLJS code; this wrapper is for ESM."
       [env effect]
       (try
         (-> (run-effect-js* (normalize-env-js env)
                             (normalize-effect-js effect))
             maybe-wallet-clj->js
             maybe-catch-runtime-error)
         (catch :default e
           (throw (runtime-error-js e)))))

     (defn apply-commands-js [state commands]
       (try
         (wallet-clj->js (apply-commands (normalize-state-js state)
                                         (normalize-commands-js commands)))
         (catch :default e
           (throw (runtime-error-js e)))))

     (def ^:export runWalletEffectJS run-effect-js)
     (def ^:export applyWalletCommandsJS apply-commands-js)))
