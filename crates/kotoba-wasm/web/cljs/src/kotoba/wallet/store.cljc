(ns kotoba.wallet.store
  "Datom wire helpers for the wallet actor.

   The wallet graph stores public/auditable facts only. Secret key material, RPC
   URLs, and signer handles stay in host capabilities."
  (:require [clojure.string :as str]))

(def schema
  {:wallet.account/id        {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :wallet.account/did       {:db/valueType :did     :db/cardinality :one}
   :wallet.account/pkh       {:db/valueType :did     :db/cardinality :one}
   :wallet.account/address   {:db/valueType :address :db/cardinality :one}
   :wallet.account/label     {:db/valueType :string  :db/cardinality :one}
   :wallet.account/custody   {:db/valueType :keyword :db/cardinality :one}
   :wallet.account/created-at {:db/valueType :long   :db/cardinality :one}

   :wallet.network/chain-id      {:db/valueType :long    :db/cardinality :one :db/unique :identity}
   :wallet.network/name          {:db/valueType :string  :db/cardinality :one}
   :wallet.network/namespace     {:db/valueType :string  :db/cardinality :one}
   :wallet.network/native-symbol {:db/valueType :string  :db/cardinality :one}
   :wallet.network/rpc-ref       {:db/valueType :string  :db/cardinality :one}
   :wallet.network/status        {:db/valueType :keyword :db/cardinality :one}

   :wallet.asset/chain    {:db/valueType :long    :db/cardinality :one}
   :wallet.asset/kind     {:db/valueType :keyword :db/cardinality :one}
   :wallet.asset/address  {:db/valueType :address :db/cardinality :one}
   :wallet.asset/symbol   {:db/valueType :string  :db/cardinality :one}
   :wallet.asset/decimals {:db/valueType :long    :db/cardinality :one}
   :wallet.asset/source   {:db/valueType :keyword :db/cardinality :one}

   :wallet.balance/account      {:db/valueType :string  :db/cardinality :one}
   :wallet.balance/chain-id     {:db/valueType :long    :db/cardinality :one}
   :wallet.balance/asset        {:db/valueType :string  :db/cardinality :one}
   :wallet.balance/block-number {:db/valueType :long    :db/cardinality :one}
   :wallet.balance/raw          {:db/valueType :uint256 :db/cardinality :one}
   :wallet.balance/observed-at  {:db/valueType :long    :db/cardinality :one}

   :wallet.allowance/account      {:db/valueType :string  :db/cardinality :one}
   :wallet.allowance/chain-id     {:db/valueType :long    :db/cardinality :one}
   :wallet.allowance/token        {:db/valueType :address :db/cardinality :one}
   :wallet.allowance/spender      {:db/valueType :address :db/cardinality :one}
   :wallet.allowance/amount       {:db/valueType :uint256 :db/cardinality :one}
   :wallet.allowance/block-number {:db/valueType :long    :db/cardinality :one}
   :wallet.allowance/observed-at  {:db/valueType :long    :db/cardinality :one}

   :wallet.quote/id             {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :wallet.quote/account        {:db/valueType :string  :db/cardinality :one}
   :wallet.quote/chain-id       {:db/valueType :long    :db/cardinality :one}
   :wallet.quote/origin         {:db/valueType :string  :db/cardinality :one}
   :wallet.quote/provider       {:db/valueType :keyword :db/cardinality :one}
   :wallet.quote/from-token     {:db/valueType :address :db/cardinality :one}
   :wallet.quote/to-token       {:db/valueType :address :db/cardinality :one}
   :wallet.quote/amount-in      {:db/valueType :uint256 :db/cardinality :one}
   :wallet.quote/min-amount-out {:db/valueType :uint256 :db/cardinality :one}
   :wallet.quote/router         {:db/valueType :address :db/cardinality :one}
   :wallet.quote/spender        {:db/valueType :address :db/cardinality :one}
   :wallet.quote/block-number   {:db/valueType :long    :db/cardinality :one}
   :wallet.quote/deadline-ms    {:db/valueType :long    :db/cardinality :one}
   :wallet.quote/request-hash   {:db/valueType :string  :db/cardinality :one}
   :wallet.quote/observed-at    {:db/valueType :long    :db/cardinality :one}

   :wallet.intent/id        {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :wallet.intent/account   {:db/valueType :string  :db/cardinality :one}
   :wallet.intent/chain-id  {:db/valueType :long    :db/cardinality :one}
   :wallet.intent/kind      {:db/valueType :keyword :db/cardinality :one}
   :wallet.intent/to        {:db/valueType :address :db/cardinality :one}
   :wallet.intent/value     {:db/valueType :uint256 :db/cardinality :one}
   :wallet.intent/data      {:db/valueType :hex     :db/cardinality :one}
   :wallet.intent/token     {:db/valueType :address :db/cardinality :one}
   :wallet.intent/recipient {:db/valueType :address :db/cardinality :one}
   :wallet.intent/spender   {:db/valueType :address :db/cardinality :one}
   :wallet.intent/amount    {:db/valueType :uint256 :db/cardinality :one}
   :wallet.intent/status    {:db/valueType :keyword :db/cardinality :one}
   :wallet.intent/origin    {:db/valueType :string  :db/cardinality :one}
   :wallet.intent/risk      {:db/valueType :keyword :db/cardinality :one}
   :wallet.intent/quote-id  {:db/valueType :string  :db/cardinality :one}
   :wallet.intent/risk-acknowledged {:db/valueType :boolean :db/cardinality :one}
   :wallet.intent/rejection-reason  {:db/valueType :string  :db/cardinality :one}
   :wallet.intent/min-amount-out {:db/valueType :uint256 :db/cardinality :one}
   :wallet.intent/slippage-bps   {:db/valueType :long    :db/cardinality :one}
   :wallet.intent/deadline-ms    {:db/valueType :long    :db/cardinality :one}
   :wallet.intent/now-ms         {:db/valueType :long    :db/cardinality :one}
   :wallet.intent/quote-mismatch-fields {:db/valueType :string :db/cardinality :one}
   :wallet.intent/payload-hash {:db/valueType :string :db/cardinality :one}
   :wallet.intent/payload-preview {:db/valueType :string :db/cardinality :one}
   :wallet.intent/hash      {:db/valueType :string  :db/cardinality :one}

   :wallet.signature/id           {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :wallet.signature/intent       {:db/valueType :string  :db/cardinality :one}
   :wallet.signature/account      {:db/valueType :string  :db/cardinality :one}
   :wallet.signature/chain-id     {:db/valueType :long    :db/cardinality :one}
   :wallet.signature/origin       {:db/valueType :string  :db/cardinality :one}
   :wallet.signature/kind         {:db/valueType :keyword :db/cardinality :one}
   :wallet.signature/payload-hash {:db/valueType :string  :db/cardinality :one}
   :wallet.signature/signature    {:db/valueType :hex     :db/cardinality :one}
   :wallet.signature/signed-at    {:db/valueType :long    :db/cardinality :one}

   :wallet.tx/hash          {:db/valueType :hex     :db/cardinality :one :db/unique :identity}
   :wallet.tx/intent        {:db/valueType :string  :db/cardinality :one}
   :wallet.tx/status        {:db/valueType :keyword :db/cardinality :one}
   :wallet.tx/nonce         {:db/valueType :long    :db/cardinality :one}
   :wallet.tx/signed-raw    {:db/valueType :hex     :db/cardinality :one}
   :wallet.tx/submitted-at  {:db/valueType :long    :db/cardinality :one}
   :wallet.tx/confirmed-at  {:db/valueType :long    :db/cardinality :one}
   :wallet.tx/block-number  {:db/valueType :long    :db/cardinality :one}
   :wallet.tx/gas-used      {:db/valueType :uint256 :db/cardinality :one}})

(defn value-type [a] (get-in schema [a :db/valueType] :string))

(defn- quote-string [s]
  (str "\"" (str/escape (str s) {\\ "\\\\" \" "\\\"" \newline "\\n" \return "\\r" \tab "\\t"}) "\""))

(defn encode-value [a v]
  (case (value-type a)
    (:string :did :address :hex :uint256) (quote-string v)
    :keyword (str v)
    :long    (str v)
    :boolean (if v "true" "false")
    (quote-string v)))

(defn datom [e a v]
  {:e e :a (str a) :v_edn (encode-value a v)})

(defn account->tx [{:keys [id did pkh address label custody created-at]}]
  (cond-> [(datom id :wallet.account/id id)
           (datom id :wallet.account/did did)
           (datom id :wallet.account/pkh pkh)
           (datom id :wallet.account/address address)
           (datom id :wallet.account/custody custody)
           (datom id :wallet.account/created-at created-at)]
    (some? label) (conj (datom id :wallet.account/label label))))

(defn network->tx [{:keys [chain-id name namespace native-symbol rpc-ref status]}]
  (let [id (str "eip155:" chain-id)]
    [(datom id :wallet.network/chain-id chain-id)
     (datom id :wallet.network/name name)
     (datom id :wallet.network/namespace (or namespace "eip155"))
     (datom id :wallet.network/native-symbol native-symbol)
     (datom id :wallet.network/rpc-ref rpc-ref)
     (datom id :wallet.network/status (or status :network.status/enabled))]))

(defn asset->tx [{:keys [chain-id kind address symbol decimals source]}]
  (let [id (str "eip155:" chain-id ":" (str/lower-case address))]
    [(datom id :wallet.asset/chain chain-id)
     (datom id :wallet.asset/kind kind)
     (datom id :wallet.asset/address address)
     (datom id :wallet.asset/symbol symbol)
     (datom id :wallet.asset/decimals decimals)
     (datom id :wallet.asset/source (or source :asset.source/user))]))

(defn balance-id [{:keys [account-id chain-id asset]}]
  (str account-id ":eip155:" chain-id ":" (str/lower-case (or asset "native"))))

(defn balance->tx [{:keys [account-id chain-id asset block-number raw observed-at] :as balance}]
  (let [id (balance-id balance)]
    [(datom id :wallet.balance/account account-id)
     (datom id :wallet.balance/chain-id chain-id)
     (datom id :wallet.balance/asset (or asset "native"))
     (datom id :wallet.balance/block-number block-number)
     (datom id :wallet.balance/raw raw)
     (datom id :wallet.balance/observed-at observed-at)]))

(defn allowance-id [{:keys [account-id chain-id token spender]}]
  (str account-id ":eip155:" chain-id ":allowance:"
       (str/lower-case token) ":" (str/lower-case spender)))

(defn allowance->tx [{:keys [account-id chain-id token spender amount block-number observed-at] :as allowance}]
  (let [id (allowance-id allowance)]
    (cond-> [(datom id :wallet.allowance/account account-id)
             (datom id :wallet.allowance/chain-id chain-id)
             (datom id :wallet.allowance/token token)
             (datom id :wallet.allowance/spender spender)
             (datom id :wallet.allowance/amount amount)]
      (some? block-number) (conj (datom id :wallet.allowance/block-number block-number))
      (some? observed-at)  (conj (datom id :wallet.allowance/observed-at observed-at)))))

(defn quote-id [{:keys [id origin chain-id from-token to-token amount-in request-hash]}]
  (or id
      (str "quote:" (hash [origin chain-id from-token to-token amount-in request-hash]))))

(defn quote->tx [{:keys [account-id chain-id origin provider from-token to-token amount-in
                         min-amount-out router spender block-number deadline-ms request-hash
                         observed-at] :as quote}]
  (let [id (quote-id quote)]
    (cond-> [(datom id :wallet.quote/id id)
             (datom id :wallet.quote/account account-id)
             (datom id :wallet.quote/chain-id chain-id)
             (datom id :wallet.quote/origin origin)
             (datom id :wallet.quote/provider provider)
             (datom id :wallet.quote/from-token from-token)
             (datom id :wallet.quote/to-token to-token)
             (datom id :wallet.quote/amount-in amount-in)
             (datom id :wallet.quote/min-amount-out min-amount-out)
             (datom id :wallet.quote/router router)
             (datom id :wallet.quote/spender spender)]
      (some? block-number) (conj (datom id :wallet.quote/block-number block-number))
      (some? deadline-ms)  (conj (datom id :wallet.quote/deadline-ms deadline-ms))
      (some? request-hash) (conj (datom id :wallet.quote/request-hash request-hash))
      (some? observed-at)  (conj (datom id :wallet.quote/observed-at observed-at)))))

(defn intent->tx [{:keys [id account-id chain-id kind to value data token recipient spender amount
                          status origin risk quote-id min-amount-out slippage-bps deadline-ms now-ms
                          quote-mismatch-fields
                          payload-hash payload-preview hash]}]
  (cond-> [(datom id :wallet.intent/id id)
           (datom id :wallet.intent/account account-id)
           (datom id :wallet.intent/chain-id chain-id)
           (datom id :wallet.intent/kind kind)
           (datom id :wallet.intent/to to)
           (datom id :wallet.intent/value (or value "0"))
           (datom id :wallet.intent/data (or data "0x"))
           (datom id :wallet.intent/status status)
           (datom id :wallet.intent/origin origin)]
    (some? token)     (conj (datom id :wallet.intent/token token))
    (some? recipient) (conj (datom id :wallet.intent/recipient recipient))
    (some? spender)   (conj (datom id :wallet.intent/spender spender))
    (some? amount)    (conj (datom id :wallet.intent/amount amount))
    (some? risk) (conj (datom id :wallet.intent/risk risk))
    (some? quote-id) (conj (datom id :wallet.intent/quote-id quote-id))
    (some? min-amount-out) (conj (datom id :wallet.intent/min-amount-out min-amount-out))
    (some? slippage-bps) (conj (datom id :wallet.intent/slippage-bps slippage-bps))
    (some? deadline-ms) (conj (datom id :wallet.intent/deadline-ms deadline-ms))
    (some? now-ms) (conj (datom id :wallet.intent/now-ms now-ms))
    (seq quote-mismatch-fields) (conj (datom id :wallet.intent/quote-mismatch-fields
                                             (pr-str quote-mismatch-fields)))
    (some? payload-hash) (conj (datom id :wallet.intent/payload-hash payload-hash))
    (some? payload-preview) (conj (datom id :wallet.intent/payload-preview payload-preview))
    (some? hash) (conj (datom id :wallet.intent/hash hash))))

(defn intent-decision->tx [{:keys [id status risk-acknowledged? reason]}]
  (cond-> [(datom id :wallet.intent/status status)]
    (some? risk-acknowledged?) (conj (datom id :wallet.intent/risk-acknowledged risk-acknowledged?))
    (some? reason) (conj (datom id :wallet.intent/rejection-reason reason))))

(defn signature->tx [{:keys [id intent-id account-id chain-id origin kind payload-hash signature signed-at]}]
  (cond-> [(datom id :wallet.signature/id id)
           (datom id :wallet.signature/intent intent-id)
           (datom id :wallet.signature/account account-id)
           (datom id :wallet.signature/chain-id chain-id)
           (datom id :wallet.signature/origin origin)
           (datom id :wallet.signature/kind kind)
           (datom id :wallet.signature/payload-hash payload-hash)
           (datom id :wallet.signature/signature signature)]
    (some? signed-at) (conj (datom id :wallet.signature/signed-at signed-at))))

(defn tx-record->tx [{:keys [hash intent-id status nonce signed-raw submitted-at
                             confirmed-at block-number gas-used]}]
  (cond-> [(datom hash :wallet.tx/hash hash)
           (datom hash :wallet.tx/intent intent-id)
           (datom hash :wallet.tx/status status)]
    (some? nonce)        (conj (datom hash :wallet.tx/nonce nonce))
    (some? signed-raw)   (conj (datom hash :wallet.tx/signed-raw signed-raw))
    (some? submitted-at) (conj (datom hash :wallet.tx/submitted-at submitted-at))
    (some? confirmed-at) (conj (datom hash :wallet.tx/confirmed-at confirmed-at))
    (some? block-number) (conj (datom hash :wallet.tx/block-number block-number))
    (some? gas-used)     (conj (datom hash :wallet.tx/gas-used gas-used))))
