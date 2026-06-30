(ns kotoba.wallet.provider
  "Pure EIP-1193 request dispatcher for the wallet actor.

   Browser CLJS can wrap this with js/Promise and event emission. This namespace
   stays pure: methods either return immediate data or an actor/effect result
   that the host must execute."
  (:require [clojure.string :as str]
            #?(:cljs [cljs.reader :as reader])
            [kotoba.wallet.actor :as actor]))

(def method->cap
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

(def eip1193-codes
  {:user-rejected 4001
   :unauthorized 4100
   :unsupported-method 4200
   :unknown-chain 4902
   :host-effect -32000
   :invalid-params -32602})

(defn provider-error
  ([kind message data]
   (ex-info message (assoc data
                           :code (get eip1193-codes kind)
                           :error-kind kind)))
  ([kind message]
   (provider-error kind message {})))

(defn hex-chain-id [chain-id]
  (str "0x" #?(:clj (Long/toHexString (long chain-id))
               :cljs (.toString chain-id 16))))

(defn parse-chain-id [chain-id]
  (try
    (let [parsed (cond
                   (integer? chain-id) chain-id
                   (and (string? chain-id) (re-matches #"0x[0-9a-fA-F]+" chain-id))
                   #?(:clj (Long/parseLong (subs chain-id 2) 16)
                      :cljs (js/parseInt (subs chain-id 2) 16))
                   (and (string? chain-id) (re-matches #"[0-9]+" chain-id))
                   #?(:clj (Long/parseLong chain-id)
                      :cljs (js/parseInt chain-id 10))
                   :else nil)]
      (when (and parsed
                 (pos? parsed)
                 #?(:clj true
                    :cljs (not (js/isNaN parsed))))
        parsed))
    (catch #?(:clj Exception :cljs :default) _
      nil)))

(defn authorized-account-addresses [state origin]
  (let [policy (get-in state [:policies origin])
        allowed (set (:accounts policy))]
    (->> (:accounts state)
         vals
         (filter #(contains? allowed (:id %)))
         (mapv :address))))

(defn provider-chain-event-payload [origin method chain-id]
  (if chain-id
    (hex-chain-id chain-id)
    (throw (provider-error :invalid-params
                           "invalid provider state selected chain"
                           {:origin origin
                            :method method
                            :reason :invalid-selected-chain-id
                            :selected-chain-id chain-id}))))

(defn provider-events
  "Derive EIP-1193 events from a pure provider transition."
  [before after result]
  (cond-> []
    (not= (:selected-chain-id before) (:selected-chain-id after))
    (conj ["chainChanged" (provider-chain-event-payload (:origin result)
                                                        (:method result)
                                                        (:selected-chain-id after))])

    (or (= "eth_requestAccounts" (:method result))
        (and (contains? result :events)
             (some #(= :account/connected (first %)) (:events result))
             (not= (authorized-account-addresses before (:origin result))
                   (authorized-account-addresses after (:origin result)))))
    (conj ["accountsChanged" (authorized-account-addresses after (:origin result))])))

(defn provider-replaced-state-events
  "Derive EIP-1193 events from a host state replacement."
  [before after origin]
  (cond-> []
    (not= (:selected-chain-id before) (:selected-chain-id after))
    (conj ["chainChanged" (provider-chain-event-payload origin
                                                        "provider.setState"
                                                        (:selected-chain-id after))])

    (not= (authorized-account-addresses before origin)
          (authorized-account-addresses after origin))
    (conj ["accountsChanged" (authorized-account-addresses after origin)])))

(defn- lower-address [address]
  (when address (str/lower-case address)))

(defn- authorized-account-ids [state origin]
  (set (get-in state [:policies origin :accounts])))

(defn- authorized-addresses [state origin]
  (set (map lower-address (authorized-account-addresses state origin))))

(defn- account-by-address [state address]
  (when address
    (some (fn [[id account]]
            (when (= (lower-address address) (lower-address (:address account)))
              (assoc account :id id)))
          (:accounts state))))

(defn- account-id-ref [state account-ref]
  (when (some? account-ref)
    (let [account-ref (str account-ref)
          account-ref-lower (lower-address account-ref)]
      (or (when (contains? (:accounts state) account-ref)
            account-ref)
          (some (fn [[id account]]
                  (when (= account-ref-lower (lower-address (:address account)))
                    id))
                (:accounts state))
          account-ref))))

(defn- account-id-match [state account-ref]
  (let [account-id (account-id-ref state account-ref)]
    (when (contains? (:accounts state) account-id)
      account-id)))

(defn- normalize-account-payload [state payload]
  (let [payload (cond-> payload
                  (contains? payload :account-id)
                  (update :account-id #(account-id-ref state %)))
        account-id (or (:account-id payload)
                       (account-id-match state (:address payload))
                       (account-id-match state (:from payload)))]
    (cond-> payload
      (some? account-id)
      (assoc :account-id account-id)

      (contains? payload :request)
      (update :request #(normalize-account-payload state %)))))

(defn- ensure-cap! [state origin method]
  (let [cap (method->cap method)
        policy (get-in state [:policies origin])
        caps (:caps policy)]
    (when-not cap
      (throw (provider-error :unsupported-method
                             "unsupported provider method"
                             {:origin origin :method method})))
    (when (and (#{:eth/accounts :eth/chain-id} cap) (nil? policy))
      nil)
    (when (and (not (#{:eth/accounts :eth/chain-id} cap)) (nil? policy))
      (throw (provider-error :unauthorized
                             "origin is not authorized for provider method"
                             {:origin origin :method method :cap cap})))
    (when (and (seq caps) (not (contains? (set caps) cap)))
      (throw (provider-error :unauthorized
                             "origin is not authorized for provider method"
                             {:origin origin :method method :cap cap})))))

(defn- ensure-chain! [state origin method chain-id]
  (let [policy (get-in state [:policies origin])
        allowed-chains (set (:chains policy))]
    (when-not (contains? (:networks state) chain-id)
      (throw (provider-error :unknown-chain
                             "network is not registered"
                             {:origin origin
                              :method method
                              :chain-id chain-id})))
    (when (and (seq allowed-chains) (not (contains? allowed-chains chain-id)))
      (throw (provider-error :unauthorized
                             "origin is not authorized for chain"
                             {:origin origin
                              :method method
                              :chain-id chain-id
                              :allowed-chains allowed-chains})))))

(declare invalid-params! selected-chain-id!)

(defn- ensure-account! [state origin method payload]
  (let [payload (normalize-account-payload state payload)
        {:keys [account-id address from]} payload
        explicit-account? (or account-id address from)
        account-id (or account-id (:selected-account-id state))
        address (or address from (get-in state [:accounts account-id :address]))
        account (get-in state [:accounts account-id])
        address-account (account-by-address state address)
        allowed-ids (authorized-account-ids state origin)
        allowed-addresses (authorized-addresses state origin)]
    (when (and (not explicit-account?) (nil? account-id))
      (invalid-params! method {:reason :invalid-selected-account-id
                               :selected-account-id account-id}))
    (when-not account
      (throw (provider-error :unauthorized
                             "wallet account is not registered"
                             {:origin origin
                              :method method
                              :account-id account-id})))
    (when (and address (nil? address-account))
      (throw (provider-error :unauthorized
                             "wallet account address is not registered"
                             {:origin origin
                              :method method
                              :address address})))
    (when (and address-account (not= account-id (:id address-account)))
      (throw (provider-error :unauthorized
                             "wallet account id does not match address"
                             {:origin origin
                              :method method
                              :account-id account-id
                              :address address
                              :address-account-id (:id address-account)})))
    (when (and (seq allowed-ids) (not (contains? allowed-ids account-id)))
      (throw (provider-error :unauthorized
                             "origin is not authorized for account"
                             (cond-> {:origin origin
                                      :method method
                                      :account-id account-id
                                      :allowed-accounts allowed-ids}
                               address (assoc :address address)))))
    (when (and address (seq allowed-addresses) (not (contains? allowed-addresses (lower-address address))))
      (throw (provider-error :unauthorized
                             "origin is not authorized for account"
                             {:origin origin
                              :method method
                              :address address
                              :allowed-addresses allowed-addresses})))))

(defn- effective-payload [payload]
  (merge payload (:request payload)))

(defn- target-chain-id [state payload]
  (let [payload (effective-payload payload)]
    (or (parse-chain-id (:chain-id payload))
        (parse-chain-id (:chainId payload))
        (:selected-chain-id state))))

(defn- target-chain-id! [method state payload]
  (let [payload (effective-payload payload)]
    (cond
      (and (contains? payload :chainId) (nil? (parse-chain-id (:chainId payload))))
      (invalid-params! method {:reason :invalid-chain-id
                               :chain-id (:chainId payload)})

      (and (contains? payload :chain-id) (nil? (parse-chain-id (:chain-id payload))))
      (invalid-params! method {:reason :invalid-chain-id
                               :chain-id (:chain-id payload)})

      (or (contains? payload :chainId)
          (contains? payload :chain-id))
      (target-chain-id state payload)

      :else
      (selected-chain-id! method state))))

(defn- first-param [params] (first (or params [])))

(defn- invalid-params! [method data]
  (throw (provider-error :invalid-params
                         "invalid provider request params"
                         (assoc data :method method))))

(defn- selected-chain-id! [method state]
  (if-let [chain-id (:selected-chain-id state)]
    chain-id
    (invalid-params! method {:reason :invalid-selected-chain-id
                             :selected-chain-id (:selected-chain-id state)})))

(defn- first-param-map! [method params]
  (let [param (first-param params)]
    (when-not (map? param)
      (invalid-params! method {:reason :first-param-must-be-map
                               :params params}))
    param))

(defn- require-fields! [method payload fields]
  (let [missing (filterv #(nil? (get payload %)) fields)]
    (when (seq missing)
      (invalid-params! method {:reason :missing-required-fields
                               :missing missing})))
  payload)

(defn- require-any-field! [method payload fields]
  (when-not (some #(some? (get payload %)) fields)
    (invalid-params! method {:reason :missing-one-of-fields
                             :fields fields}))
  payload)

(defn- chain-id! [method chain-id]
  (let [parsed (parse-chain-id chain-id)]
    (when-not parsed
      (invalid-params! method {:reason :invalid-chain-id
                               :chain-id chain-id}))
    parsed))

(defn- nonblank-string? [x]
  (and (string? x) (not (str/blank? x))))

(defn- rpc-url? [x]
  (and (nonblank-string? x)
       (boolean (re-matches #"https?://.+" x))))

(defn- native-symbol [native-currency]
  (or (get native-currency :symbol)
      (get native-currency "symbol")))

(defn- address-like? [x]
  (and (string? x) (boolean (re-matches #"0x[0-9a-fA-F]{40}" x))))

(defn- validate-add-chain-payload! [method payload]
  (let [native-currency (:nativeCurrency payload)
        rpc-urls (:rpcUrls payload)
        symbol (native-symbol native-currency)]
    (chain-id! method (:chainId payload))
    (when-not (nonblank-string? (:chainName payload))
      (invalid-params! method {:reason :invalid-chain-name
                               :field :chainName}))
    (when-not (map? native-currency)
      (invalid-params! method {:reason :native-currency-must-be-map
                               :field :nativeCurrency}))
    (when-not (nonblank-string? symbol)
      (invalid-params! method {:reason :missing-native-currency-symbol
                               :field :nativeCurrency.symbol}))
    (when-not (and (sequential? rpc-urls)
                   (seq rpc-urls)
                   (every? rpc-url? rpc-urls))
      (invalid-params! method {:reason :invalid-rpc-urls
                               :field :rpcUrls}))
    payload))

(defn add-chain-payload [{:keys [chainId chainName nativeCurrency rpcUrls]}]
  {:chain-id (parse-chain-id chainId)
   :name chainName
   :namespace "eip155"
   :native-symbol (native-symbol nativeCurrency)
   :rpc-ref (str "provider:" (parse-chain-id chainId) ":" (hash rpcUrls))
   :status :network.status/enabled})

(defn- supported-asset-type? [type]
  (contains? #{"ERC20" "ERC721" "ERC1155"} type))

(defn- valid-decimals? [x]
  (and (integer? x) (<= 0 x 255)))

(defn- validate-watch-asset-payload! [method {:keys [type options] :as payload}]
  (when-not (supported-asset-type? type)
    (invalid-params! method {:reason :unsupported-asset-type
                             :field :type
                             :type type}))
  (when-not (map? options)
    (invalid-params! method {:reason :options-must-be-map
                             :field :options}))
  (require-fields! method options [:address])
  (when-not (address-like? (:address options))
    (invalid-params! method {:reason :invalid-asset-address
                             :field :options.address
                             :address (:address options)}))
  (when (= "ERC20" type)
    (when-not (nonblank-string? (:symbol options))
      (invalid-params! method {:reason :missing-asset-symbol
                               :field :options.symbol}))
    (when-not (valid-decimals? (:decimals options))
      (invalid-params! method {:reason :invalid-asset-decimals
                               :field :options.decimals
                               :decimals (:decimals options)})))
  payload)

(defn watch-asset-payload [chain-id {:keys [type options]}]
  {:chain-id chain-id
   :kind (case type
           "ERC20" :asset.kind/erc20
           "ERC721" :asset.kind/erc721
           "ERC1155" :asset.kind/erc1155
           :asset.kind/unknown)
   :address (or (:address options) (get options "address"))
   :symbol (or (:symbol options) (get options "symbol"))
   :decimals (or (:decimals options) (get options "decimals") 0)
   :source :asset.source/provider})

(defn personal-sign-payload [state origin params]
  (let [[a b] (or params [])
        address-count (count (filter address-like? [a b]))
        _ (when (not= 1 address-count)
            (invalid-params! "personal_sign" {:reason :exactly-one-address-required
                                              :params params}))
        [address message] (if (address-like? a) [a b] [b a])]
    {:kind :intent.kind/message-sign
     :origin origin
     :chain-id (:selected-chain-id state)
     :address address
     :payload message
     :payload-hash (str "personal-sign:" (hash [origin (:selected-chain-id state) address message]))}))

(defn typed-data-sign-payload [state origin params]
  (let [[address typed-data] (or params [])]
    (when-not (address-like? address)
      (invalid-params! "eth_signTypedData_v4" {:reason :first-param-must-be-address
                                               :address address}))
    {:kind :intent.kind/typed-data-sign
     :origin origin
     :chain-id (:selected-chain-id state)
     :address address
     :payload typed-data
     :payload-hash (str "typed-data-v4:" (hash [origin (:selected-chain-id state) address typed-data]))}))

(defn request
  "Dispatch one EIP-1193 request.

   Returns:
   - {:state state :result value :events [] :effects [] :datoms []} for immediate methods
   - actor/step-shaped maps plus :result for methods that create actor events/effects"
  [state origin {:keys [method params]}]
  (ensure-cap! state origin method)
  (case method
    "eth_accounts"
    {:state state :result (authorized-account-addresses state origin) :events [] :effects [] :datoms []}

    "eth_requestAccounts"
    {:state state :result (authorized-account-addresses state origin) :events [] :effects [] :datoms []}

    "eth_chainId"
    {:state state :result (hex-chain-id (selected-chain-id! method state)) :events [] :effects [] :datoms []}

    "wallet_switchEthereumChain"
    (let [param (require-fields! method (first-param-map! method params) [:chainId])
          chain-id (chain-id! method (:chainId param))
          _ (ensure-chain! state origin method chain-id)
          result (actor/step state [:wallet/select-network {:chain-id chain-id}])]
      (assoc result :result nil))

    "wallet_addEthereumChain"
    (let [param (require-fields! method (first-param-map! method params) [:chainId])
          _ (validate-add-chain-payload! method param)
          payload (add-chain-payload param)
          result (actor/step state [:wallet/add-network payload])]
      (assoc result :result nil))

    "wallet_watchAsset"
    (let [selected-chain-id (selected-chain-id! method state)
          _ (ensure-chain! state origin method selected-chain-id)
          param (require-fields! method (first-param-map! method params) [:type :options])
          _ (validate-watch-asset-payload! method param)
          payload (watch-asset-payload selected-chain-id param)
          result (actor/step state [:wallet/watch-asset payload])]
      (assoc result :result true))

    "eth_call"
    (let [tx-param (first-param-map! method params)
          chain-id (target-chain-id! method state tx-param)]
      (ensure-chain! state origin method chain-id)
      (ensure-account! state origin method tx-param)
      {:state state
       :result nil
       :events []
       :datoms []
       :effects [{:effect :evm-rpc/call
                  :chain-id chain-id
                  :origin origin
                  :params params}]})

    "eth_estimateGas"
    (let [tx-param (first-param-map! method params)
          chain-id (target-chain-id! method state tx-param)]
      (ensure-chain! state origin method chain-id)
      (ensure-account! state origin method tx-param)
      {:state state
       :result nil
       :events []
       :datoms []
       :effects [{:effect :evm-rpc/estimate-gas
                  :chain-id chain-id
                  :origin origin
                  :params params}]})

    "eth_sendTransaction"
    (let [param (first-param-map! method params)
          _ (require-any-field! method param [:to :data])
          chain-id (target-chain-id! method state param)
          tx-map (normalize-account-payload state
                                            (assoc param
                                                   :origin origin
                                                   :id (str "intent:" (hash [origin params]))
                                                   :chain-id chain-id))
          _ (ensure-chain! state origin method chain-id)
          _ (ensure-account! state origin method tx-map)
          result (actor/step state [:wallet/prepare-contract-call tx-map])]
      (assoc result :result nil))

    "wallet_prepareTransfer"
    (let [param (require-fields! method (first-param-map! method params) [:to :amount])
          chain-id (target-chain-id! method state param)
          payload (normalize-account-payload state
                                             (assoc param
                                                    :origin origin
                                                    :id (str "transfer:" (hash [origin params]))
                                                    :chain-id chain-id))
          _ (ensure-chain! state origin method chain-id)
          _ (ensure-account! state origin method payload)
          result (actor/step state [:wallet/prepare-transfer payload])]
      (assoc result :result (get-in result [:events 0 1 :id])))

    "wallet_revokeApproval"
    (let [param (require-fields! method (first-param-map! method params) [:token :spender])
          chain-id (target-chain-id! method state param)
          payload (normalize-account-payload state
                                             (assoc param
                                                    :origin origin
                                                    :id (str "revoke:" (hash [origin params]))
                                                    :chain-id chain-id))
          _ (ensure-chain! state origin method chain-id)
          _ (ensure-account! state origin method payload)
          result (actor/step state [:wallet/revoke-approval payload])]
      (assoc result :result (get-in result [:events 0 1 :id])))

    "wallet_quoteSwap"
    (let [payload (normalize-account-payload
                   state
                   (require-fields! method (first-param-map! method params)
                                    [:from-token :to-token :amount-in]))
          chain-id (target-chain-id! method state payload)
          request (normalize-account-payload
                   state
                   (assoc payload
                          :origin origin
                          :account-id (or (:account-id (effective-payload payload))
                                          (:selected-account-id state))
                          :chain-id chain-id))]
      (ensure-chain! state origin method chain-id)
      (ensure-account! state origin method request)
      {:state state
       :result nil
       :events []
       :datoms []
       :effects [{:effect :wallet/quote-swap
                  :origin origin
                  :chain-id chain-id
                  :request request}]})

    "wallet_prepareSwap"
    (let [param (normalize-account-payload state (first-param-map! method params))
          request (require-fields! method (:request param) [:from-token :to-token :amount-in])
          _ (require-fields! method param [:quote])
          chain-id (target-chain-id! method state param)
          effective (effective-payload param)
          account-id (or (:account-id effective)
                         (:selected-account-id state))
          payload (normalize-account-payload
                   state
                   (assoc param
                          :request request
                          :origin origin
                          :id (str "swap:" (hash [origin params]))
                          :account-id account-id
                          :chain-id chain-id))
          _ (ensure-chain! state origin method (target-chain-id! method state payload))
          _ (ensure-account! state origin method (effective-payload payload))
          result (actor/step state [:wallet/prepare-swap payload])]
      (assoc result :result (mapv (comp :id second) (:events result))))

    "personal_sign"
    (let [selected-chain-id (selected-chain-id! method state)
          _ (ensure-chain! state origin method selected-chain-id)
          _ (when (< (count (or params [])) 2)
              (invalid-params! method {:reason :missing-required-fields
                                       :missing [:address :payload]}))
          payload (normalize-account-payload
                   state
                   (assoc (personal-sign-payload state origin params)
                          :id (str "sign:" (hash [origin method params]))))
          _ (require-fields! method payload [:address :payload])
          _ (ensure-account! state origin method payload)
          result (actor/step state [:wallet/prepare-signature payload])]
      (assoc result :result (get-in result [:events 0 1 :id])))

    "eth_signTypedData_v4"
    (let [selected-chain-id (selected-chain-id! method state)
          _ (ensure-chain! state origin method selected-chain-id)
          _ (when (< (count (or params [])) 2)
              (invalid-params! method {:reason :missing-required-fields
                                       :missing [:address :payload]}))
          payload (normalize-account-payload
                   state
                   (assoc (typed-data-sign-payload state origin params)
                          :id (str "typed:" (hash [origin method params]))))
          _ (require-fields! method payload [:address :payload])
          _ (ensure-account! state origin method payload)
          result (actor/step state [:wallet/prepare-signature payload])]
      (assoc result :result (get-in result [:events 0 1 :id])))

    (throw (provider-error :unsupported-method
                           "unsupported provider method"
                           {:origin origin :method method}))))

#?(:cljs
   (do
     (defn- camel->kebab [s]
       (-> s
           (str/replace #"([a-z0-9])([A-Z])" "$1-$2")
           str/lower-case))

     (defn- keywordize-record-keys [m]
       (into {}
             (map (fn [[k v]]
                    [(keyword (camel->kebab (str k))) v]))
             (or m {})))

     (defn- normalize-js-key [k]
       (if (keyword? k)
         (keyword (camel->kebab (name k)))
         (keyword (camel->kebab (str k)))))

     (defn- maybe-keyword-value [x]
       (if (and (string? x)
                (boolean (re-matches #"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+" x)))
         (let [[ns name] (str/split x #"/" 2)]
           (keyword ns name))
         x))

     (defn- normalize-provider-js-value [x]
       (cond
         (map? x)
         (into {}
               (map (fn [[k v]]
                      [(normalize-js-key k) (normalize-provider-js-value v)]))
               x)

         (vector? x)
         (mapv normalize-provider-js-value x)

         (seq? x)
         (mapv normalize-provider-js-value x)

         :else (maybe-keyword-value x)))

     (defn- normalize-chain-id-fields [x]
       (cond
         (map? x)
         (into {}
               (map (fn [[k v]]
                      [k (if (= :chain-id k)
                           (or (parse-chain-id v) v)
                           (normalize-chain-id-fields v))]))
               x)

         (vector? x)
         (mapv normalize-chain-id-fields x)

         (seq? x)
         (mapv normalize-chain-id-fields x)

         :else x))

     (defn- provider-command-tuple! [command]
       (when-not (and (vector? command) (= 2 (count command)))
         (throw (ex-info "wallet command must be a two-item tuple"
                         {:kind :wallet.command/malformed
                          :actual command})))
       command)

     (defn- normalize-provider-command-js [command]
       (let [[event payload] (provider-command-tuple! command)]
         [(maybe-keyword-value event)
          (normalize-chain-id-fields (normalize-provider-js-value payload))]))

     (defn- normalize-provider-commands-js [commands]
       (let [commands (js->clj commands :keywordize-keys true)]
         (when-not (vector? commands)
           (throw (ex-info "wallet commands must be an array"
                           {:kind :wallet.commands/malformed
                            :actual commands})))
         (mapv normalize-provider-command-js commands)))

     (defn- apply-provider-commands [state commands]
       (reduce (fn [{:keys [state] :as acc} command]
                 (let [result (actor/step state command)]
                   (-> acc
                       (assoc :state (:state result))
                       (update :events into (:events result))
                       (update :effects into (:effects result))
                       (update :datoms into (:datoms result)))))
               {:state state :events [] :effects [] :datoms []}
               commands))

     (defn- cap-keyword [cap]
       (cond
         (keyword? cap) cap
         (contains? method->cap cap) (get method->cap cap)
         (and (string? cap) (str/includes? cap "/"))
         (let [[ns name] (str/split cap #"/" 2)]
           (keyword ns name))
         (string? cap) (keyword "eth" cap)
         :else cap))

     (defn- normalize-record-map [m field method]
       (when (and (some? m)
                  (not (map? m)))
         (throw (provider-error :invalid-params
                                (str "wallet " field " must be an object")
                                {:method method
                                 :reason (keyword (str "invalid-" field))
                                 :actual m})))
       (into {}
             (map (fn [[k v]]
                    [(str k) (normalize-provider-js-value v)]))
             (or m {})))

     (defn- maybe-composite-key [k]
       (if (and (string? k) (str/starts-with? k "["))
         (try
           (let [v (reader/read-string k)]
             (if (vector? v) v k))
           (catch :default _
             k))
         k))

     (defn- normalize-composite-key-map [m field method]
       (when (and (some? m)
                  (not (map? m)))
         (throw (provider-error :invalid-params
                                (str "wallet " field " must be an object")
                                {:method method
                                 :reason (keyword (str "invalid-" field))
                                 :actual m})))
       (into {}
             (map (fn [[k v]]
                    [(maybe-composite-key (str k)) (normalize-provider-js-value v)]))
             (or m {})))

     (defn- normalize-accounts [accounts method]
       (when (and (some? accounts)
                  (not (map? accounts)))
         (throw (provider-error :invalid-params
                                "wallet accounts must be an object"
                                {:method method
                                 :reason :invalid-accounts
                                 :actual accounts})))
       (into {}
             (map (fn [[k v]]
                    (let [record (normalize-provider-js-value v)
                          id (or (:id record) (str k))]
                      [id (assoc record :id id)])))
             (or accounts {})))

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

     (defn- normalize-networks [networks method]
       (when (and (some? networks)
                  (not (map? networks)))
         (throw (provider-error :invalid-params
                                "wallet networks must be an object"
                                {:method method
                                 :reason :invalid-networks
                                 :actual networks})))
       (into {}
             (keep (fn [[k v]]
                     (let [record (normalize-provider-js-value v)
                           chain-id (or (parse-chain-id (:chain-id record))
                                        (parse-chain-id k))]
                       (when chain-id
                         [chain-id (assoc record :chain-id chain-id)]))))
             (or networks {})))

     (defn- normalize-policies [accounts policies method]
       (when (and (some? policies)
                  (not (map? policies)))
         (throw (provider-error :invalid-params
                                "wallet policies must be an object"
                                {:method method
                                 :reason :invalid-policies
                                 :actual policies})))
       (into {}
             (map (fn [[k v]]
                    (let [record (normalize-provider-js-value v)
                          origin (or (:origin record) (str k))]
                      (when (or (not (string? origin))
                                (str/blank? origin))
                        (throw (provider-error :invalid-params
                                               "wallet policy origin must be a non-empty string"
                                               {:method method
                                                :reason :invalid-policy-origin
                                                :origin origin})))
                      [origin (-> record
                                  (assoc :origin origin)
                                  (update :accounts #(mapv (partial policy-account-id accounts) (or % [])))
                                  (update :chains #(vec (keep parse-chain-id (or % []))))
                                  (update :caps #(vec (distinct (map cap-keyword (or % []))))))])))
             (or policies {})))

     (defn- js-state->wallet-state
       ([state]
        (js-state->wallet-state state "wallet-state"))
       ([state method]
        (let [raw (js->clj state)]
          (when-not (map? raw)
            (throw (provider-error :invalid-params
                                   "wallet state must be an object"
                                   {:method method
                                    :reason :invalid-state
                                    :actual raw})))
          (let [selected-account-ref (or (get raw "selected-account-id")
                                         (get raw "selectedAccountId"))
                selected-chain-id (parse-chain-id (or (get raw "selected-chain-id")
                                                      (get raw "selectedChainId")))
                accounts (normalize-accounts (get raw "accounts") method)
                selected-account-id (policy-account-id accounts selected-account-ref)]
            (-> actor/empty-state
                (merge (keywordize-record-keys raw))
                (assoc :accounts accounts
                       :networks (normalize-networks (get raw "networks") method)
                       :policies (normalize-policies accounts (get raw "policies") method)
                       :intents (normalize-record-map (get raw "intents") "intents" method)
                       :txs (normalize-record-map (get raw "txs") "txs" method)
                       :quotes (normalize-record-map (get raw "quotes") "quotes" method)
                       :signatures (normalize-record-map (get raw "signatures") "signatures" method)
                       :assets (normalize-composite-key-map (get raw "assets") "assets" method)
                       :allowances (normalize-composite-key-map (get raw "allowances") "allowances" method)
                       :balances (normalize-composite-key-map (get raw "balances") "balances" method)
                       :selected-account-id selected-account-id
                       :selected-chain-id selected-chain-id))))))

     (defn- normalize-provider-result-js [r]
       (let [raw (js->clj r :keywordize-keys true)
             normalized (normalize-provider-js-value raw)]
         (when-not (map? normalized)
           (throw (ex-info "wallet host result must be an object"
                           {:kind :wallet.host-result/malformed
                            :actual normalized})))
         (when (and (contains? raw :state)
                    (not (map? (:state raw))))
           (throw (ex-info "wallet host state must be an object"
                           {:kind :wallet.host-state/malformed
                            :actual (:state raw)})))
         (cond-> normalized
           (contains? raw :state)
           (assoc :state (js-state->wallet-state (clj->js (:state raw)) "hostEffect.state"))

           (contains? raw :commands)
           (assoc :commands (normalize-provider-commands-js (:commands raw))))))

     (defn- provider-error-js [e]
       (let [data (ex-data e)]
         (if (:code data)
           (let [err (js/Error. (.-message e))]
             (set! (.-code err) (:code data))
             (set! (.-data err) (clj->js data))
             err)
           e)))

     (defn- keyword->js-string [k]
       (if-let [ns (namespace k)]
         (str ns "/" (name k))
         (name k)))

     (defn- provider-clj->js [x]
       (cond
         (keyword? x)
         (keyword->js-string x)

         (map? x)
         (clj->js (into {}
                       (map (fn [[k v]]
                              [(if (keyword? k) (name k) k)
                               (provider-clj->js v)]))
                       x))

         (vector? x)
         (clj->js (mapv provider-clj->js x))

         (seq? x)
         (clj->js (mapv provider-clj->js x))

         :else x))

     (defn- host-effect-error-js [origin method e]
       (let [message (or (.-message e) "wallet host effect failed")
             host-data (ex-data e)
             data (cond-> {:code (get eip1193-codes :host-effect)
                           :error-kind :host-effect
                           :origin origin
                           :method method
                           :message message}
                    host-data
                    (assoc :host-error-data host-data))
             err (js/Error. message)]
         (set! (.-code err) (:code data))
         (set! (.-data err) (provider-clj->js data))
         err))

     (defn- emit! [listeners event payload]
       (doseq [f (get @listeners event)]
         (try
           (f (provider-clj->js payload))
           (catch :default _
             nil))))

     (defn- changed-events [before after result]
       (provider-events before after result))

     (defn- replaced-state-events [before after origin]
       (provider-replaced-state-events before after origin))

     (defn- default-browser-origin []
       (when (exists? js/window)
         (.. js/window -location -origin)))

     (defn- js-origin->provider-origin [origin method]
       (when (or (not (string? origin))
                 (str/blank? origin))
         (throw (provider-error :invalid-params
                                "wallet provider origin must be a non-empty string"
                                {:method method
                                 :reason :invalid-origin})))
       origin)

     (defn- js-request->provider-request [req]
       (let [req* (js->clj req :keywordize-keys true)
             _ (when-not (map? req*)
                 (throw (provider-error :invalid-params
                                        "wallet provider request must be an object"
                                        {:method "provider.request"
                                         :reason :invalid-request})))
             method* (:method req*)
             _ (when (or (not (string? method*))
                         (str/blank? method*))
                 (throw (provider-error :invalid-params
                                        "wallet provider request method must be a non-empty string"
                                        {:method "provider.request"
                                         :reason :invalid-method
                                         :actual method*})))
             params* (:params req*)]
         (when (and (contains? req* :params)
                    (not (or (vector? params*) (map? params*))))
           (throw (provider-error :invalid-params
                                  "wallet provider request params must be an array or object"
                                  {:method method*
                                   :reason :invalid-request-params
                                   :actual params*})))
         req*))

     (defn request-js
       "JS-facing EIP-1193 dispatcher. Accepts JS state/request, returns JS result map.
       The caller owns state persistence and host-effect execution."
       [state origin req]
       (try
         (provider-clj->js (request (js-state->wallet-state state "walletRequest.state")
                                    (js-origin->provider-origin origin "walletRequest")
                                    (js-request->provider-request req)))
         (catch :default e
           (throw (provider-error-js e)))))

     (defn create-provider-js
       "Create a minimal stateful EIP-1193 provider object.

        env:
          state          initial CLJS/JS wallet state
          origin         dapp origin
          handleEffects  optional JS fn(resultMap) -> Promise/resultMap. Host can
                         execute effects and return an updated result map.

       The provider keeps state locally, emits chainChanged/accountsChanged, and
       exposes getState/setState for the embedding app. Network/signing remain
       injected host work."
       [env]
       (try
         (let [env* (js->clj env :keywordize-keys true)
               _ (when-not (map? env*)
                   (throw (provider-error :invalid-params
                                          "wallet provider env must be an object"
                                          {:method "createWalletProvider"
                                           :reason :invalid-env
                                           :actual env*})))
              state* (atom (if (contains? env* :state)
                             (js-state->wallet-state (.-state env) "createWalletProvider.state")
                             actor/empty-state))
              origin* (:origin env*)
              _ (when (and (contains? env* :origin)
                           (or (not (string? origin*))
                               (str/blank? origin*)))
                  (throw (provider-error :invalid-params
                                         "wallet provider origin must be a non-empty string"
                                         {:method "createWalletProvider"
                                          :reason :invalid-origin})))
              origin (or origin* (default-browser-origin))
              _ (when (or (not (string? origin))
                          (str/blank? origin))
                  (throw (provider-error :invalid-params
                                         "wallet provider origin is required outside browser contexts"
                                         {:method "createWalletProvider"
                                          :reason :invalid-origin})))
              listeners (atom {})
              handle-effects (:handleEffects env*)
              _ (when (and (contains? env* :handleEffects)
                           (not (fn? handle-effects)))
                  (throw (provider-error :invalid-params
                                         "wallet provider handleEffects must be a function"
                                         {:method "createWalletProvider"
                                          :reason :invalid-handle-effects})))]
           (letfn [(request* [req]
                     (js/Promise.
                      (fn [resolve reject]
                        (try
                          (let [req* (js-request->provider-request req)
                                before @state*
                                result (assoc (request before origin req*) :origin origin :method (:method req*))
                                finish (fn [r]
                                         (let [r* (if (some? r)
                                                    (merge result (normalize-provider-result-js r))
                                                    result)
                                               after* (or (:state r*) (:state result))
                                               applied (when (seq (:commands r*))
                                                         (apply-provider-commands after* (:commands r*)))
                                               r* (if applied
                                                    (-> r*
                                                        (assoc :state (:state applied))
                                                        (update :events into (:events applied))
                                                        (update :effects into (:effects applied))
                                                        (update :datoms into (:datoms applied)))
                                                    r*)
                                               after (or (:state r*) after*)
                                               events (changed-events before after r*)]
                                           (reset! state* after)
                                           (doseq [[event payload] events]
                                             (emit! listeners event payload))
                                           (resolve (provider-clj->js (:result r*)))))]
                            (if (and handle-effects (seq (:effects result)))
                              (try
                                (-> (.resolve js/Promise (handle-effects (provider-clj->js result)))
                                    (.then finish)
                                    (.catch (fn [e]
                                              (reject (host-effect-error-js origin (:method req*) e)))))
                                (catch :default e
                                  (reject (host-effect-error-js origin (:method req*) e))))
                              (finish result)))
                          (catch :default e
                            (reject (provider-error-js e)))))))
                  (on* [event f]
                     (when (or (not (string? event))
                               (str/blank? event))
                       (throw (provider-error-js
                               (provider-error :invalid-params
                                               "wallet provider event must be a non-empty string"
                                               {:method "provider.on"
                                                :reason :invalid-event
                                                :event event}))))
                     (when-not (fn? f)
                       (throw (provider-error-js
                               (provider-error :invalid-params
                                               "wallet provider listener must be a function"
                                               {:method "provider.on"
                                                :reason :invalid-listener
                                                :event event}))))
                     (swap! listeners update event (fnil conj []) f)
                     nil)
                  (remove-listener* [event f]
                     (when (or (not (string? event))
                               (str/blank? event))
                       (throw (provider-error-js
                               (provider-error :invalid-params
                                               "wallet provider event must be a non-empty string"
                                               {:method "provider.removeListener"
                                                :reason :invalid-event
                                                :event event}))))
                     (when-not (fn? f)
                       (throw (provider-error-js
                               (provider-error :invalid-params
                                               "wallet provider listener must be a function"
                                               {:method "provider.removeListener"
                                                :reason :invalid-listener
                                                :event event}))))
                     (swap! listeners
                            (fn [m]
                              (let [remaining (vec (remove #{f} (get m event)))]
                                (if (seq remaining)
                                  (assoc m event remaining)
                                  (dissoc m event)))))
                     nil)
                  (set-state* [s]
                     (try
                       (let [before @state*
                             after (js-state->wallet-state s "provider.setState")
                             events (replaced-state-events before after origin)]
                         (reset! state* after)
                         (doseq [[event payload] events]
                           (emit! listeners event payload)))
                       (catch :default e
                         (throw (provider-error-js e))))
                     nil)]
             #js {:request request*
                  :on on*
                  :removeListener remove-listener*
                  :getState (fn [] (provider-clj->js @state*))
                  :setState set-state*}))
         (catch :default e
           (throw (provider-error-js e)))))

     (def ^:export requestJS request-js)
     (def ^:export createWalletProviderJS create-provider-js)))
