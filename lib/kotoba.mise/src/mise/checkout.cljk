(ns mise.checkout
  "Checkout flow state machine + payment port (pure).

  A Checkout is {:stage :contact :shipping :payment :cart :order-id}. Stages
  advance :contact → :shipping → :payment → :review → :confirmed. Fields are
  free-form maps the host fills; validate-stage checks required keys per stage.

  IPaymentPort is an injected adapter (authorize/capture). v1 ships a mock
  adapter that always authorizes. Stripe/live adapters are follow-ups.

  Portable .cljc, zero host effects."
  (:require [kotoba.lang.text :as str]
            [mise.pricing :as pricing]
            [mise.cart :as cart]
            [mise.order :as order]))

(def stages [:contact :shipping :payment :review :confirmed])

(def required-fields
  {:contact    #{:email :name}
   :shipping   #{:address :city :postal :country}
   :payment    #{:payment-method-ref}
   :review     #{}})

(defrecord Checkout [stage contact shipping payment cart order-id])

(defn checkout
  "Start a checkout for a cart at the :contact stage."
  ([cart]
   (checkout cart {}))
  ([cart fields]
   (->Checkout :contact
               (:contact fields {})
               (:shipping fields {})
               (:payment fields {})
               cart
               nil)))

(defn stage-index
  "Index of a stage in `stages`, or nil if unknown."
  [stage]
  (loop [i 0 [s & rest] stages]
    (cond
      (nil? s) nil
      (= s stage) i
      :else (recur (inc i) rest))))

(defn- next-after [stage]
  (let [i (stage-index stage)]
    (when (and i (< i (dec (count stages))))
      (nth stages (inc i)))))

(defn stage-fields
  "The merged fields for a stage from a checkout."
  [checkout stage]
  (case stage
    :contact  (:contact checkout)
    :shipping (:shipping checkout)
    :payment  (:payment checkout)
    {}))

;; ---------------------------------------------------------------------------
;; shipping address validation
;; ---------------------------------------------------------------------------

(defn postal-valid?
  "Stub postal format check: non-blank and 3-10 chars with no whitespace runs.
  v1 does NOT verify country-specific formats (JP 〒XXX-XXXX, US ZIP, etc.) —
  the host app injects a real validator. This just rejects obviously-bad input."
  [postal]
  (let [s (str postal)]
    (and (<= 3 (count s) 10)
         (not (re-find #"\s\s" s))
         (re-find #"[0-9]" s))))

(def no-postal-code-countries
  "ISO 3166-1 alpha-2 codes for countries that operate **no postal code
  system at all** (UPU postal-code列 が空の国、抜粋)。

  Requiring a postal code unconditionally made these destinations
  unshippable: a Hong Kong customer with a complete, deliverable address
  was told `{:postal \"required\"}` and could not get past the shipping
  step. That is not a strict validator, it is a country blocklist that
  nobody wrote down.

  The list is deliberately data, not a regex, so a host can extend it
  without patching the validator."
  #{"AE" "AG" "AO" "AW" "BF" "BI" "BJ" "BS" "BW" "BZ" "CD" "CF" "CG" "CI"
    "CK" "CM" "DJ" "DM" "ER" "FJ" "GD" "GH" "GM" "GQ" "GY" "HK" "JM" "KI"
    "KM" "KN" "KP" "LC" "LY" "ML" "MO" "MR" "MW" "NR" "NU" "QA" "RW" "SB"
    "SC" "SL" "SO" "SR" "ST" "SY" "TL" "TO" "TT" "TV" "TZ" "UG" "VU" "WS"
    "YE" "ZW"})

(defn postal-required?
  "Does this destination country use postal codes at all? Unknown/blank
  countries default to `true` — the common case is that a code exists."
  [country]
  (not (contains? no-postal-code-countries (str/upper (str/trim (str country))))))

(defn email-valid?
  "Email format check: a non-blank local part with no whitespace, '@', and a
  domain ending in a dot-suffix of at least two letters.

  The previous version only asked whether '@' appeared *somewhere* and
  whether the string ended in a TLD-looking suffix, so `\"@.com\"`,
  `\"@@@.com\"` and `\"a b@x.com\"` were all accepted — an address with no
  local part passes every downstream check and then bounces silently at
  send time, after the order is already placed."
  [email]
  (boolean (re-matches #"[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}" (str email))))

(defn validate-shipping-address
  "Return a map of {:field → error-message} for invalid shipping fields. Empty
  map = all valid. Checks required presence + email/postal format."
  [shipping]
  (let [country (:country shipping)
        need-postal? (postal-required? country)
        required (cond-> [:address :city :country]
                   need-postal? (conj :postal))
        missing (into {} (for [k required
                               :when (str/blank? (get shipping k))]
                           [k "required"]))
        bad-postal (when (and (not (str/blank? (:postal shipping)))
                              (not (postal-valid? (:postal shipping))))
                     {:postal "invalid format"})]
    (merge missing bad-postal)))

(defn shipping-valid?
  "True if the shipping address passes validation (no errors)."
  [shipping]
  (empty? (validate-shipping-address shipping)))

(defn validate-stage
  "Return nil if the stage's required fields are present AND well-formed,
  else a seq of invalid field keys (missing, or present but failing format
  validation -- email-valid? for :contact, validate-shipping-address for
  :shipping). A nil/empty result means the stage is valid. Format checks
  used to be dead code from this gating path: next-stage only ever checked
  presence, so a malformed email/postal code sailed straight through to
  :payment/:review/place-order despite email-valid?/postal-valid? already
  existing and correctly rejecting it when called directly."
  [checkout stage]
  (let [required (get required-fields stage #{})
        fields (stage-fields checkout stage)
        missing (filter #(not (contains? fields %)) required)
        invalid (case stage
                  :contact  (when (and (contains? fields :email)
                                       (not (email-valid? (:email fields))))
                              [:email])
                  :shipping (keys (validate-shipping-address fields))
                  nil)]
    (seq (distinct (concat missing invalid)))))

(defn set-field
  "Set a single field in the current stage's field map. Returns a new Checkout."
  [checkout stage key value]
  (case stage
    :contact  (assoc checkout :contact (assoc (:contact checkout) key value))
    :shipping (assoc checkout :shipping (assoc (:shipping checkout) key value))
    :payment  (assoc checkout :payment (assoc (:payment checkout) key value))
    checkout))

(defn set-fields
  "Merge a map into a stage's fields."
  [checkout stage m]
  (reduce-kv (fn [c k v] (set-field c stage k v)) checkout m))

(defn next-stage
  "Advance to the next stage if the current one validates; returns
  {:ok checkout} or {:errors [..] checkout}. Never skips :confirmed."
  [checkout]
  (let [stage (:stage checkout)]
    (if (= stage :confirmed)
      {:ok checkout}
      (if-let [missing (validate-stage checkout stage)]
        {:errors missing :checkout checkout}
        (if-let [nxt (next-after stage)]
          {:ok (assoc checkout :stage nxt)}
          {:ok checkout})))))

(defn prev-stage
  "Go back one stage (clamped at :contact)."
  [checkout]
  (let [i (stage-index (:stage checkout))]
    (if (or (nil? i) (<= i 0))
      checkout
      (assoc checkout :stage (nth stages (dec i))))))

;; ---------------------------------------------------------------------------
;; payment port
;; ---------------------------------------------------------------------------

(defprotocol IPaymentPort
  (authorize [this ctx amount]
    "Reserve `amount` for the order. Returns a PaymentRef map {:ref :status
    :amount} where :status is :authorized | :declined | :failed. Pure (mock) or
    side-effectful (real adapter — wrap in host effect).")
  (capture [this ctx ref]
    "Settle an authorized payment. Returns an updated PaymentRef."))

(defrecord MockPaymentPort []
  IPaymentPort
  (authorize [_ ctx amount]
    {:ref (str "mock_" (hash ctx) "_" (hash amount))
     :status :authorized
     :amount amount})
  (capture [_ _ ref]
    (assoc ref :status :captured)))

(defn mock-payment-port [] (->MockPaymentPort))

;; ---------------------------------------------------------------------------
;; place order
;; ---------------------------------------------------------------------------

(defn place-order
  "Finalize a :review-stage checkout into an Order via the payment port.
  Returns {:ok order} on success or {:error msg :checkout checkout}. The
  checkout must be at :review; caller advances through stages first."
  [checkout payment-port opts]
  (let [{:keys [discount tax shipping ctx order-id-fn]
         :or {discount (pricing/no-discount)
              tax (pricing/flat-tax 0.0)
              shipping (pricing/free-shipping)
              order-id-fn #(str "ord_" (hash %))}} opts
        cart (:cart checkout)
        totals (cart/totals cart {:discount discount :tax tax
                                  :shipping shipping :ctx ctx})
        amount (:total totals)]
    (if (not= (:stage checkout) :review)
      {:error "checkout not at review stage" :checkout checkout}
      (let [pref (authorize payment-port (or ctx {}) amount)]
        (if (= (:status pref) :authorized)
          (let [ord (order/map->Order
                     {:id (order-id-fn checkout)
                      :items (:lines cart)
                      :shipping (:shipping checkout)
                      :contact (:contact checkout)
                      :payment-ref pref
                      :status :pending
                      :totals totals})]
            {:ok (assoc checkout :stage :confirmed :order-id (:id ord)) :order ord})
          {:error (:status pref) :checkout checkout})))))
