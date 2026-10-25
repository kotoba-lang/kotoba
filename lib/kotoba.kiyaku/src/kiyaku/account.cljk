(ns kiyaku.account
  "Customer account + address book (pure). Account{:id :email :name :addresses
  :payment-method-refs :wallet-balance :created-at}. Address{:id :label :line1
  :city :postal :country :default?}. The end-customer counterpart to
  chobo.tenant (which is the operator). Projects to chobo.ledger lane :customer."
  (:require [kotoba.lang.text :as str]
            [chobo.ledger :as ledger]))

(defrecord Account [id email name addresses payment-method-refs wallet-balance created-at])
(defrecord Address [id label line1 line2 city postal country default?])

(defn account [m] (merge {:addresses [] :payment-method-refs [] :wallet-balance 0} m))

(defn add-address [acc addr]
  (update acc :addresses conj (map->Address addr)))

(defn default-address [acc]
  (some #(when (:default? %) %) (:addresses acc [])))

(defn set-default-address [acc addr-id]
  (update acc :addresses (fn [xs] (mapv #(assoc % :default? (= (:id %) addr-id)) xs))))

(defn add-payment-method [acc ref] (update acc :payment-method-refs conj ref))

(defn adjust-wallet [acc amount] (update acc :wallet-balance (fnil + 0) amount))

(defn customer-activity
  "Project a customer-account event onto chobo.ledger as a :customer activity."
  [acc opts]
  (ledger/activity
   (merge {:lane :customer :kind :account
           :title (:email acc) :props {:account-id (:id acc)}} opts)))

;; ---------------------------------------------------------------------------
;; wallet transactions (credit/debit ledger on the account)
;; ---------------------------------------------------------------------------

(defrecord WalletTx [id type amount reason at])

(defn wallet-tx [m] (merge {:type :credit} m))

(defn wallet-balance
  "Compute balance from a seq of WalletTx (credits add, debits subtract)."
  [txs]
  (reduce (fn [bal {:keys [type amount]}]
            (if (= type :debit) (- bal (or amount 0)) (+ bal (or amount 0))))
          0 txs))

(defn apply-wallet-tx
  "Record a wallet transaction on an account: adjust :wallet-balance and append
  to :wallet-ledger. Returns the updated account."
  [acc tx]
  (let [tx (map->WalletTx tx)
        delta (if (= (:type tx) :debit) (- (:amount tx 0)) (:amount tx 0))]
    (-> acc
        (update :wallet-balance (fnil + 0) delta)
        (update :wallet-ledger (fnil conj []) tx))))

(defn wallet-ledger [acc] (:wallet-ledger acc []))

(defn wallet-txs-by-type [acc type]
  (filterv #(= (:type %) type) (wallet-ledger acc)))

;; ---------------------------------------------------------------------------
;; address validation (postal/country format stubs)
;; ---------------------------------------------------------------------------

(def country-codes
  "A minimal set of ISO 3166-1 alpha-2 country codes for validation."
  #{"JP" "US" "GB" "DE" "FR" "CN" "KR" "AU" "CA" "IT" "ES" "NL" "SE" "BR" "IN"})

(defn valid-country?
  "True if the country code is a known ISO 3166-1 alpha-2 code (uppercase)."
  [country]
  (let [c (if (keyword? country) (name country) (str country))]
    (contains? country-codes (str/upper c))))

(defn postal-format-for
  "Return a regex matching the postal format for a country, or nil if unknown."
  [country]
  (let [c (if (keyword? country) (name country) (str country))]
    (case (str/upper c)
      "JP" #"\d{3}-\d{4}"
      "US" #"\d{5}(-\d{4})?"
      "GB" #"[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}"
      "CA" #"[A-Z]\d[A-Z]\s?\d[A-Z]\d"
      "DE" #"\d{5}"
      "FR" #"\d{5}"
      nil)))

(defn valid-postal?
  "True if the postal code matches the country's format. Unknown country → just
  non-blank."
  [postal country]
  (let [pat (postal-format-for country)]
    (if pat
      (boolean (and postal (re-matches pat (str postal))))
      (and postal (not (str/blank? (str postal)))))))

(defn validate-address
  "Return a map of {:field → error} for invalid address fields. Empty = valid."
  [addr]
  (let [errors (atom {})]
    (when (str/blank? (:line1 addr)) (swap! errors assoc :line1 "required"))
    (when (str/blank? (:city addr)) (swap! errors assoc :city "required"))
    (when (str/blank? (:country addr))
      (swap! errors assoc :country "required"))
    (when (and (not (str/blank? (:country addr)))
               (not (valid-country? (:country addr))))
      (swap! errors assoc :country "unknown country code"))
    (when (and (not (str/blank? (:postal addr)))
               (not (str/blank? (:country addr)))
               (not (valid-postal? (:postal addr) (:country addr))))
      (swap! errors assoc :postal "invalid format for country"))
    @errors))

(defn address-valid?
  "True if the address passes validation."
  [addr]
  (empty? (validate-address addr)))
