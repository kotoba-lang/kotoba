(ns kotoba.wallet.actor
  "Pure command/event wallet actor. Hosts run effects; this namespace only
   validates commands and updates projected state."
  (:require [kotoba.wallet.risk :as risk]
            [kotoba.wallet.store :as store]
            [kotoba.wallet.swap :as swap]
            [kotoba.wallet.tx :as tx]))

(def empty-state
  {:accounts {}
   :networks {}
   :assets {}
   :policies {}
   :intents {}
   :txs {}
   :quotes {}
   :signatures {}
   :selected-account-id nil
   :selected-chain-id nil
   :allowances {}
   :balances {}})

(defn- decision-state [status payload]
  (cond-> {:status status}
    (contains? payload :risk-acknowledged?) (assoc :risk-acknowledged? (:risk-acknowledged? payload))
    (contains? payload :reason) (assoc :rejection-reason (:reason payload))))

(defn apply-event [state [event payload]]
  (case event
    :account/connected
    (-> state
        (assoc-in [:accounts (:id payload)] payload)
        (assoc :selected-account-id (:id payload)))

    :network/added
    (assoc-in state [:networks (:chain-id payload)] payload)

    :network/selected
    (assoc state :selected-chain-id (:chain-id payload))

    :policy/granted
    (assoc-in state [:policies (:origin payload)] payload)

    :asset/watched
    (assoc-in state [:assets [(:chain-id payload) (:address payload)]] payload)

    :intent/created
    (assoc-in state [:intents (:id payload)] payload)

    :intent/approved
    (update-in state [:intents (:id payload)] merge
               (decision-state :intent.status/approved payload))

    :intent/rejected
    (update-in state [:intents (:id payload)] merge
               (decision-state :intent.status/rejected payload))

    :allowance/observed
    (assoc-in state [:allowances [(:account-id payload) (:chain-id payload)
                                  (:token payload) (:spender payload)]]
              (:amount payload))

    :balance/observed
    (assoc-in state [:balances [(:account-id payload) (:chain-id payload) (or (:asset payload) "native")]]
              payload)

    :quote/observed
    (assoc-in state [:quotes (:id payload)] payload)

    :message/signed
    (-> state
        (assoc-in [:signatures (:id payload)] payload)
        (assoc-in [:intents (:intent-id payload) :status] :intent.status/signed))

    :tx/signed
    (assoc-in state [:txs (:hash payload)] payload)

    :tx/submitted
    (-> state
        (assoc-in [:txs (:hash payload)] payload)
        (assoc-in [:intents (:intent-id payload) :status] :intent.status/submitted))

    :tx/confirmed
    (-> state
        (assoc-in [:txs (:hash payload)] payload)
        (assoc-in [:intents (:intent-id payload) :status] :intent.status/confirmed))

    state))

(defn event->datoms [[event payload]]
  (case event
    :account/connected (store/account->tx payload)
    :network/added     (store/network->tx payload)
    :asset/watched     (store/asset->tx payload)
    :allowance/observed (store/allowance->tx payload)
    :balance/observed  (store/balance->tx payload)
    :quote/observed    (store/quote->tx payload)
    :intent/created    (store/intent->tx payload)
    :intent/approved   (store/intent-decision->tx (assoc payload :status :intent.status/approved))
    :intent/rejected   (store/intent-decision->tx (assoc payload :status :intent.status/rejected))
    :message/signed    (concat (store/signature->tx payload)
                               (store/intent-decision->tx {:id (:intent-id payload)
                                                           :status :intent.status/signed}))
    :tx/signed         (store/tx-record->tx payload)
    :tx/submitted      (concat (store/tx-record->tx payload)
                               (store/intent-decision->tx {:id (:intent-id payload)
                                                           :status :intent.status/submitted}))
    :tx/confirmed      (concat (store/tx-record->tx payload)
                               (store/intent-decision->tx {:id (:intent-id payload)
                                                           :status :intent.status/confirmed}))
    []))

(defn- emit [state events effects]
  (let [state' (reduce apply-event state events)]
    {:state state'
     :events events
     :effects effects
     :datoms (vec (mapcat event->datoms events))}))

(defn- intent-with-id [prefix idx chain-id account-id origin intent]
  (let [id (str prefix ":" idx)
        base (-> intent
                 (assoc :account-id account-id
                        :origin origin)
                 (update :value #(or % "0"))
                 (update :data #(if (keyword? %) (str %) %)))
        normalized (merge base
                          (tx/normalize-tx chain-id base)
                          {:kind (:kind intent)})]
    (tx/tx->intent id normalized)))

(defn- transfer-intent [chain-id account-id origin {:keys [asset to amount token] :as payload}]
  (let [native? (or (= asset :native) (= asset "native") (nil? token))
        base (if native?
               {:kind :intent.kind/native-transfer
                :to to
                :recipient to
                :amount (str amount)
                :value (str amount)
                :data "0x"}
               {:kind :intent.kind/erc20-transfer
                :to token
                :token token
                :recipient to
                :amount (str amount)
                :value "0"
                :data ":erc20.transfer/exact"})]
    (merge base
           (select-keys payload [:gas :gas-limit :max-fee-per-gas :max-priority-fee-per-gas])
           {:chain-id chain-id
            :account-id account-id
            :origin origin})))

(defn- revoke-approval-intent [chain-id account-id origin {:keys [token spender] :as payload}]
  (merge {:kind :intent.kind/erc20-revoke-approval
          :to token
          :token token
          :spender spender
          :amount "0"
          :value "0"
          :data ":erc20.approve/zero"
          :chain-id chain-id
          :account-id account-id
          :origin origin}
         (select-keys payload [:gas :gas-limit :max-fee-per-gas :max-priority-fee-per-gas])))

(defn- payload-preview [payload]
  (let [s (str payload)]
    (str "payload:" (cond
                      (map? payload) "map"
                      (sequential? payload) "seq"
                      (string? payload) "string"
                      :else (str (type payload)))
         ":len=" (count s))))

(defn- sign-intent [chain-id account-id origin {:keys [kind address payload payload-hash] :as request}]
  {:kind kind
   :to address
   :value "0"
   :data "0x"
   :chain-id chain-id
   :account-id account-id
   :origin origin
   :payload payload
   :payload-hash (or payload-hash (str "payload:" (hash [kind origin chain-id account-id address payload])))
   :payload-preview (payload-preview payload)
   :address address})

(defn- intent-command-payload [payload]
  (if (map? payload) payload {:id payload}))

(defn- pending-intent! [state payload]
  (let [{:keys [id]} (intent-command-payload payload)
        intent (get-in state [:intents id])]
    (when-not intent
      (throw (ex-info "wallet intent is not found" {:id id})))
    (when-not (= :intent.status/pending-user (:status intent))
      (throw (ex-info "wallet intent is not pending user approval"
                      {:id id :status (:status intent)})))
    intent))

(defn- approvable-intent! [state payload]
  (let [{:keys [id risk-acknowledged?]} (intent-command-payload payload)
        intent (pending-intent! state payload)]
    (when-let [fatal-risks (seq (cond-> []
                                  (seq (:quote-mismatch-fields intent))
                                  (conj :risk/quote-request-mismatch)

                                  (and (:deadline-ms intent)
                                       (:now-ms intent)
                                       (> (:now-ms intent) (:deadline-ms intent)))
                                  (conj :risk/quote-expired)))]
      (throw (ex-info "wallet intent has fatal risk and cannot be approved"
                      {:id id
                       :kind :wallet.intent/fatal-risk
                       :risks (vec fatal-risks)})))
    (when (and (= :risk.level/high (:risk intent))
               (not risk-acknowledged?))
      (throw (ex-info "wallet high-risk intent requires explicit acknowledgement"
                      {:id id
                       :risk (:risk intent)
                       :required :risk-acknowledged?})))
    intent))

(defn- observed-intent! [state id allowed-statuses observation]
  (let [intent (get-in state [:intents id])
        allowed (set allowed-statuses)]
    (when-not intent
      (throw (ex-info "wallet observation references unknown intent"
                      {:id id :observation observation})))
    (when-not (contains? allowed (:status intent))
      (throw (ex-info "wallet observation is not valid for intent status"
                      {:id id
                       :status (:status intent)
                       :allowed-statuses allowed
                       :observation observation})))
    intent))

(defn- uint256-decimal? [v]
  (let [s (cond
            (integer? v) (str v)
            (string? v) v
            :else nil)
        digits (when (and s (re-matches #"[0-9]+" s))
                 (if-let [trimmed (seq (drop-while #(= \0 %) s))]
                   (apply str trimmed)
                   "0"))
        max-digits swap/max-uint256]
    (boolean
     (and digits
          (not (pos? (compare [(count digits) digits]
                              [(count max-digits) max-digits])))))))

(defn- hex-prefixed? [v]
  (and (string? v)
       (re-matches #"0x.+" v)))

(defn- hex-string? [v]
  (and (string? v)
       (re-matches #"0x.*" v)))

(defn- address-like? [v]
  (and (string? v)
       (re-matches #"0x[0-9a-fA-F]+" v)))

(defn- nonblank-string? [v]
  (and (string? v)
       (boolean (seq v))))

(defn- positive-integer? [v]
  (and (integer? v) (pos? v)))

(defn- zero-or-positive-integer? [v]
  (and (integer? v) (not (neg? v))))

(defn- valid-decimals? [v]
  (and (zero-or-positive-integer? v) (<= v 255)))

(defn- invalid-command! [kind field actual]
  (throw (ex-info "wallet command has invalid payload"
                  {:kind kind
                   :field field
                   :actual actual})))

(defn- require-command-fields! [payload kind fields]
  (when-let [missing (seq (swap/missing-fields payload fields))]
    (throw (ex-info "wallet command is missing required fields"
                    {:kind kind
                     :missing (vec missing)}))))

(defn- network-command! [payload]
  (require-command-fields! payload :wallet.network/missing-fields
                           [:chain-id :name :native-symbol :rpc-ref])
  (when-not (positive-integer? (:chain-id payload))
    (invalid-command! :wallet.network/chain-id :chain-id (:chain-id payload)))
  (when-not (nonblank-string? (:name payload))
    (invalid-command! :wallet.network/name :name (:name payload)))
  (when-not (nonblank-string? (:native-symbol payload))
    (invalid-command! :wallet.network/native-symbol :native-symbol (:native-symbol payload)))
  (when-not (nonblank-string? (:rpc-ref payload))
    (invalid-command! :wallet.network/rpc-ref :rpc-ref (:rpc-ref payload)))
  payload)

(defn- asset-command! [payload]
  (require-command-fields! payload :wallet.asset/missing-fields
                           [:chain-id :kind :address :symbol :decimals])
  (when-not (positive-integer? (:chain-id payload))
    (invalid-command! :wallet.asset/chain-id :chain-id (:chain-id payload)))
  (when-not (contains? #{:asset.kind/erc20 :asset.kind/erc721 :asset.kind/erc1155}
                       (:kind payload))
    (invalid-command! :wallet.asset/kind :kind (:kind payload)))
  (when-not (address-like? (:address payload))
    (invalid-command! :wallet.asset/address :address (:address payload)))
  (when-not (nonblank-string? (:symbol payload))
    (invalid-command! :wallet.asset/symbol :symbol (:symbol payload)))
  (when-not (valid-decimals? (:decimals payload))
    (invalid-command! :wallet.asset/decimals :decimals (:decimals payload)))
  payload)

(defn- connect-command! [payload]
  (require-command-fields! payload :wallet.connect/missing-fields
                           [:account :origin :chains :requested])
  (let [account (:account payload)]
    (when-not (map? account)
      (invalid-command! :wallet.connect/account :account account))
    (require-command-fields! account :wallet.connect.account/missing-fields
                             [:id :address :pkh])
    (when-not (nonblank-string? (:id account))
      (invalid-command! :wallet.connect/account-id :id (:id account)))
    (when-not (address-like? (:address account))
      (invalid-command! :wallet.connect/account-address :address (:address account)))
    (when-not (nonblank-string? (:pkh account))
      (invalid-command! :wallet.connect/account-pkh :pkh (:pkh account))))
  (when-not (nonblank-string? (:origin payload))
    (invalid-command! :wallet.connect/origin :origin (:origin payload)))
  (when-not (and (sequential? (:chains payload))
                 (seq (:chains payload))
                 (every? positive-integer? (:chains payload)))
    (invalid-command! :wallet.connect/chains :chains (:chains payload)))
  (when-not (and (sequential? (:requested payload))
                 (seq (:requested payload))
                 (every? keyword? (:requested payload)))
    (invalid-command! :wallet.connect/requested :requested (:requested payload)))
  (when (and (contains? payload :max-slippage-bps)
             (not (and (zero-or-positive-integer? (:max-slippage-bps payload))
                       (<= (:max-slippage-bps payload) 10000))))
    (invalid-command! :wallet.connect/max-slippage-bps
                      :max-slippage-bps
                      (:max-slippage-bps payload)))
  payload)

(declare uint256-decimal?)

(defn- optional-positive-command-integer! [payload kind field]
  (when (and (contains? payload field)
             (not (positive-integer? (get payload field))))
    (invalid-command! kind field (get payload field))))

(defn- optional-nonblank-command-string! [payload kind field]
  (when (and (contains? payload field)
             (not (nonblank-string? (get payload field))))
    (invalid-command! kind field (get payload field))))

(defn- optional-hex-command-string! [payload kind field]
  (when (and (contains? payload field)
             (not (hex-prefixed? (get payload field))))
    (invalid-command! kind field (get payload field))))

(defn- optional-hex-command-value! [payload kind field]
  (when (and (contains? payload field)
             (not (hex-string? (get payload field))))
    (invalid-command! kind field (get payload field))))

(defn- optional-uint256-command! [payload kind field]
  (when (and (contains? payload field)
             (not (uint256-decimal? (get payload field))))
    (invalid-command! kind field (get payload field))))

(defn- optional-evm-value-command! [payload kind field]
  (when (and (contains? payload field)
             (not (or (uint256-decimal? (get payload field))
                      (hex-string? (get payload field)))))
    (invalid-command! kind field (get payload field))))

(defn- intent-command-common! [payload missing-kind]
  (require-command-fields! payload missing-kind [:id])
  (when-not (nonblank-string? (:id payload))
    (invalid-command! missing-kind :id (:id payload)))
  (optional-nonblank-command-string! payload missing-kind :origin)
  (optional-nonblank-command-string! payload missing-kind :account-id)
  (optional-positive-command-integer! payload missing-kind :chain-id)
  payload)

(defn- contract-call-command! [payload]
  (intent-command-common! payload :wallet.contract-call/missing-fields)
  (when-not (or (contains? payload :to) (contains? payload :data))
    (throw (ex-info "wallet command is missing required fields"
                    {:kind :wallet.contract-call/missing-fields
                     :missing [:to :data]})))
  (optional-hex-command-string! payload :wallet.contract-call/to :to)
  (optional-hex-command-value! payload :wallet.contract-call/data :data)
  (optional-evm-value-command! payload :wallet.contract-call/value :value)
  payload)

(defn- transfer-command! [payload]
  (intent-command-common! payload :wallet.transfer/missing-fields)
  (require-command-fields! payload :wallet.transfer/missing-fields [:to :amount])
  (optional-hex-command-string! payload :wallet.transfer/to :to)
  (optional-hex-command-string! payload :wallet.transfer/token :token)
  (optional-uint256-command! payload :wallet.transfer/amount :amount)
  payload)

(defn- revoke-command! [payload]
  (intent-command-common! payload :wallet.revoke/missing-fields)
  (require-command-fields! payload :wallet.revoke/missing-fields [:token :spender])
  (optional-hex-command-string! payload :wallet.revoke/token :token)
  (optional-hex-command-string! payload :wallet.revoke/spender :spender)
  payload)

(defn- signature-command! [payload]
  (intent-command-common! payload :wallet.signature/missing-fields)
  (require-command-fields! payload :wallet.signature/missing-fields [:kind :address :payload])
  (when-not (contains? #{:intent.kind/message-sign :intent.kind/typed-data-sign}
                       (:kind payload))
    (invalid-command! :wallet.signature/kind :kind (:kind payload)))
  (when-not (address-like? (:address payload))
    (invalid-command! :wallet.signature/address :address (:address payload)))
  (optional-nonblank-command-string! payload :wallet.signature/payload-hash :payload-hash)
  payload)

(defn- select-network-command! [payload]
  (require-command-fields! payload :wallet.select-network/missing-fields [:chain-id])
  (when-not (positive-integer? (:chain-id payload))
    (invalid-command! :wallet.select-network/chain-id :chain-id (:chain-id payload)))
  payload)

(defn- intent-decision-command! [payload command]
  (let [payload (intent-command-payload payload)
        kind (case command
               :wallet/approve-intent :wallet.approve-intent/missing-fields
               :wallet/reject-intent :wallet.reject-intent/missing-fields)]
    (require-command-fields! payload kind [:id])
    (when-not (nonblank-string? (:id payload))
      (invalid-command! kind :id (:id payload)))
    (when (and (contains? payload :risk-acknowledged?)
               (not (boolean? (:risk-acknowledged? payload))))
      (invalid-command! :wallet.approve-intent/risk-acknowledged?
                        :risk-acknowledged?
                        (:risk-acknowledged? payload)))
    (when (and (= :wallet/reject-intent command)
               (contains? payload :reason)
               (not (nonblank-string? (:reason payload))))
      (invalid-command! :wallet.reject-intent/reason :reason (:reason payload)))
    payload))

(defn- sync-command! [payload]
  (require-command-fields! payload :wallet.sync/missing-fields [:chain-id])
  (when-not (positive-integer? (:chain-id payload))
    (invalid-command! :wallet.sync/chain-id :chain-id (:chain-id payload)))
  (optional-nonblank-command-string! payload :wallet.sync/account-id :account-id)
  (optional-nonblank-command-string! payload :wallet.sync/origin :origin)
  payload)

(def balance-observation-fields
  [:account-id :chain-id :block-number :raw :observed-at])

(def allowance-observation-fields
  [:account-id :chain-id :token :spender :amount :block-number :observed-at])

(defn- required-observation! [payload observation fields]
  (when-let [missing (seq (swap/missing-fields payload fields))]
    (throw (ex-info "wallet observation is missing required fields"
                    {:observation observation
                     :kind :wallet.observation/missing-fields
                     :missing (vec missing)}))))

(defn- positive-observation-integer! [payload observation field]
  (when-not (positive-integer? (get payload field))
    (throw (ex-info "wallet observation has invalid positive integer field"
                    {:observation observation
                     :field field
                     :actual (get payload field)}))))

(defn- uint256-observation! [payload observation field]
  (when-not (uint256-decimal? (get payload field))
    (throw (ex-info "wallet observation has invalid uint256 field"
                    {:observation observation
                     :field field
                     :actual (get payload field)}))))

(defn- balance-observation! [payload]
  (required-observation! payload :balance/observed balance-observation-fields)
  (positive-observation-integer! payload :balance/observed :chain-id)
  (positive-observation-integer! payload :balance/observed :block-number)
  (positive-observation-integer! payload :balance/observed :observed-at)
  (uint256-observation! payload :balance/observed :raw)
  payload)

(defn- allowance-observation! [payload]
  (required-observation! payload :allowance/observed allowance-observation-fields)
  (positive-observation-integer! payload :allowance/observed :chain-id)
  (positive-observation-integer! payload :allowance/observed :block-number)
  (positive-observation-integer! payload :allowance/observed :observed-at)
  (uint256-observation! payload :allowance/observed :amount)
  payload)

(defn- tx-observation! [payload observation]
  (when-not (:hash payload)
    (throw (ex-info "wallet tx observation is missing tx hash"
                    {:observation observation
                     :field :hash
                     :intent-id (:intent-id payload)})))
  (when-not (hex-prefixed? (:hash payload))
    (throw (ex-info "wallet tx observation has invalid tx hash"
                    {:observation observation
                     :field :hash
                     :intent-id (:intent-id payload)
                     :actual (:hash payload)})))
  (when (and (= :tx/signed observation)
             (not (:signed-raw payload)))
    (throw (ex-info "wallet signed tx observation is missing signed raw transaction"
                    {:observation observation
                     :field :signed-raw
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)})))
  (when (and (= :tx/signed observation)
             (not (hex-prefixed? (:signed-raw payload))))
    (throw (ex-info "wallet signed tx observation has invalid signed raw transaction"
                    {:observation observation
                     :field :signed-raw
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)
                     :actual (:signed-raw payload)})))
  (when (and (= :tx/submitted observation)
             (not (:submitted-at payload)))
    (throw (ex-info "wallet submitted tx observation is missing submitted timestamp"
                    {:observation observation
                     :field :submitted-at
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)})))
  (when (and (= :tx/submitted observation)
             (not (and (integer? (:submitted-at payload))
                       (pos? (:submitted-at payload)))))
    (throw (ex-info "wallet submitted tx observation has invalid submitted timestamp"
                    {:observation observation
                     :field :submitted-at
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)
                     :actual (:submitted-at payload)})))
  (when (and (= :tx/confirmed observation)
             (not (:block-number payload)))
    (throw (ex-info "wallet confirmed tx observation is missing block number"
                    {:observation observation
                     :field :block-number
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)})))
  (when (and (= :tx/confirmed observation)
             (not (and (integer? (:block-number payload))
                       (pos? (:block-number payload)))))
    (throw (ex-info "wallet confirmed tx observation has invalid block number"
                    {:observation observation
                     :field :block-number
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)
                     :actual (:block-number payload)})))
  (when (and (= :tx/confirmed observation)
             (contains? payload :gas-used)
             (not (uint256-decimal? (:gas-used payload))))
    (throw (ex-info "wallet confirmed tx observation has invalid gas used"
                    {:observation observation
                     :field :gas-used
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)
                     :actual (:gas-used payload)})))
  (when (and (= :tx/confirmed observation)
             (contains? payload :confirmed-at)
             (not (positive-integer? (:confirmed-at payload))))
    (throw (ex-info "wallet confirmed tx observation has invalid confirmed timestamp"
                    {:observation observation
                     :field :confirmed-at
                     :intent-id (:intent-id payload)
                     :hash (:hash payload)
                     :actual (:confirmed-at payload)})))
  payload)

(defn- signature-observation! [intent payload observation]
  (when-not (:signature payload)
    (throw (ex-info "wallet signature observation is missing signature"
                    {:observation observation
                     :field :signature
                     :intent-id (:intent-id payload)})))
  (when-not (hex-prefixed? (:signature payload))
    (throw (ex-info "wallet signature observation has invalid signature"
                    {:observation observation
                     :field :signature
                     :intent-id (:intent-id payload)
                     :actual (:signature payload)})))
  (when-not (:payload-hash payload)
    (throw (ex-info "wallet signature observation is missing payload hash"
                    {:observation observation
                     :field :payload-hash
                     :intent-id (:intent-id payload)})))
  (when-not (= (:payload-hash intent) (:payload-hash payload))
    (throw (ex-info "wallet signature observation payload hash mismatch"
                    {:observation observation
                     :kind :wallet.signature/payload-hash
                     :intent-id (:intent-id payload)
                     :expected (:payload-hash intent)
                     :actual (:payload-hash payload)})))
  (when (and (contains? payload :signed-at)
             (not (positive-integer? (:signed-at payload))))
    (throw (ex-info "wallet signature observation has invalid signed timestamp"
                    {:observation observation
                     :field :signed-at
                     :intent-id (:intent-id payload)
                     :actual (:signed-at payload)})))
  payload)

(defn- ensure-new-intent! [state id]
  (when (get-in state [:intents id])
    (throw (ex-info "wallet intent id already exists" {:id id}))))

(defn- ensure-new-intents! [state intents]
  (doseq [id (map :id intents)]
    (ensure-new-intent! state id)))

(defn step [state [command payload]]
  (case command
    :wallet/connect
    (let [_ (connect-command! payload)
          account (:account payload)
          origin (:origin payload)
          policy {:origin origin
                  :accounts [(:id account)]
                  :chains (:chains payload)
                  :caps (set (:requested payload))
                  :max-slippage-bps (or (:max-slippage-bps payload) 100)
                  :allow-unlimited-approval? false}]
      (emit state [[:account/connected account]
                   [:policy/granted policy]]
            []))

    :wallet/add-network
    (let [_ (network-command! payload)]
      (emit state [[:network/added payload]] []))

    :wallet/select-network
    (let [_ (select-network-command! payload)]
      (if (contains? (:networks state) (:chain-id payload))
        (emit state [[:network/selected payload]] [])
        (throw (ex-info "network is not registered" payload))))

    :wallet/watch-asset
    (let [_ (asset-command! payload)]
      (emit state [[:asset/watched payload]] []))

    :wallet/prepare-contract-call
    (let [id (:id payload)
          _ (contract-call-command! payload)
          _ (ensure-new-intent! state id)
          account-id (:account-id payload (:selected-account-id state))
          chain-id (:chain-id payload (:selected-chain-id state))
          normalized (tx/normalize-tx chain-id
                                      (assoc payload :account-id account-id))
          intent (tx/tx->intent id normalized)
          assessed (risk/assess state intent)
          intent (assoc intent :risk (:level assessed))]
      (emit state [[:intent/created intent]]
            [{:effect :evm/simulate
              :intent intent
              :risk assessed}]))

    :wallet/prepare-transfer
    (let [id (:id payload)
          _ (transfer-command! payload)
          _ (ensure-new-intent! state id)
          origin (:origin payload)
          account-id (:account-id payload (:selected-account-id state))
          chain-id (:chain-id payload (:selected-chain-id state))
          transfer (transfer-intent chain-id account-id origin payload)
          normalized (merge (tx/normalize-tx chain-id transfer) transfer)
          intent (tx/tx->intent id normalized)
          assessed (risk/assess state intent)
          intent (assoc intent :risk (:level assessed))]
      (emit state [[:intent/created intent]]
            [{:effect :evm/simulate
              :intent intent
              :risk assessed}]))

    :wallet/revoke-approval
    (let [id (:id payload)
          _ (revoke-command! payload)
          _ (ensure-new-intent! state id)
          origin (:origin payload)
          account-id (:account-id payload (:selected-account-id state))
          chain-id (:chain-id payload (:selected-chain-id state))
          revoke (revoke-approval-intent chain-id account-id origin payload)
          normalized (merge (tx/normalize-tx chain-id revoke) revoke)
          intent (tx/tx->intent id normalized)
          assessed (risk/assess state intent)
          intent (assoc intent :risk (:level assessed))]
      (emit state [[:intent/created intent]]
            [{:effect :evm/simulate
              :intent intent
              :risk assessed}]))

    :wallet/prepare-swap
    (let [origin (:origin payload)
          account-id (or (:account-id payload)
                         (get-in payload [:request :account-id])
                         (:selected-account-id state))
          chain-id (or (:chain-id payload)
                       (get-in payload [:request :chain-id])
                       (:selected-chain-id state))
          request (assoc (:request payload)
                         :origin origin
                         :account-id account-id
                         :chain-id chain-id
                         :now-ms (or (:now-ms payload)
                                     (get-in payload [:request :now-ms])))
          quote (merge (select-keys request [:origin :account-id :chain-id :from-token :to-token :amount-in
                                             :request-hash])
                       (:quote payload))
          quote (assoc quote :id (store/quote-id quote))
          plan (swap/plan state quote request)
          prefix (or (:id payload) (str "swap:" (hash [origin request quote])))
          intents (map-indexed #(intent-with-id prefix %1 chain-id account-id origin %2)
                               (:intents plan))
          _ (ensure-new-intents! state intents)
          assessed (map #(risk/assess state %) intents)
          intents (mapv (fn [intent risk-result]
                          (assoc intent :risk (:level risk-result)))
                        intents assessed)]
      (emit state
            (mapv (fn [intent] [:intent/created intent]) intents)
            (mapv (fn [intent risk-result]
                    {:effect :evm/simulate
                     :intent intent
                     :risk risk-result
                     :swap-plan plan})
                  intents assessed)))

    :wallet/prepare-signature
    (let [id (:id payload)
          _ (signature-command! payload)
          _ (ensure-new-intent! state id)
          origin (:origin payload)
          account-id (:account-id payload (:selected-account-id state))
          chain-id (:chain-id payload (:selected-chain-id state))
          intent (tx/tx->intent id (sign-intent chain-id account-id origin payload))
          assessed (risk/assess state intent)
          intent (assoc intent :risk (:level assessed))]
      (emit state [[:intent/created intent]]
            [{:effect :wallet/review-signature
              :intent intent
              :risk assessed}]))

    :wallet/approve-intent
    (let [payload (intent-decision-command! payload command)
          intent (approvable-intent! state payload)]
      (emit state [[:intent/approved payload]]
            [{:effect (if (#{:intent.kind/message-sign :intent.kind/typed-data-sign} (:kind intent))
                        :wallet/sign-message
                        :wallet/sign-and-submit)
              :intent intent}]))

    :wallet/message-signed
    (let [intent (observed-intent! state (:intent-id payload) #{:intent.status/approved} :message/signed)
          _ (signature-observation! intent payload :message/signed)]
      (emit state [[:message/signed (assoc payload :status :signature.status/signed)]] []))

    :wallet/tx-signed
    (let [_ (observed-intent! state (:intent-id payload) #{:intent.status/approved} :tx/signed)
          _ (tx-observation! payload :tx/signed)]
      (emit state [[:tx/signed (assoc payload :status :tx.status/signed)]] []))

    :wallet/tx-submitted
    (let [_ (observed-intent! state (:intent-id payload) #{:intent.status/approved} :tx/submitted)
          _ (tx-observation! payload :tx/submitted)]
      (emit state [[:tx/submitted (assoc payload :status :tx.status/submitted)]] []))

    :wallet/tx-confirmed
    (let [_ (observed-intent! state (:intent-id payload) #{:intent.status/submitted} :tx/confirmed)
          _ (tx-observation! payload :tx/confirmed)]
      (emit state [[:tx/confirmed (assoc payload :status :tx.status/confirmed)]] []))

    :wallet/reject-intent
    (let [payload (intent-decision-command! payload command)
          _ (pending-intent! state payload)]
      (emit state [[:intent/rejected payload]] []))

    :wallet/sync
    (let [_ (sync-command! payload)]
      (emit state [] [{:effect :wallet/sync :request payload}]))

    :wallet/observe-balance
    (let [_ (balance-observation! payload)]
      (emit state [[:balance/observed payload]] []))

    :wallet/observe-allowance
    (let [_ (allowance-observation! payload)]
      (emit state [[:allowance/observed payload]] []))

    :wallet/quote-observed
    (let [_ (swap/ensure-observed-quote! payload)
          id (store/quote-id payload)]
      (emit state [[:quote/observed (assoc payload :id id)]] []))

    (throw (ex-info "unknown wallet command" {:command command :payload payload}))))
