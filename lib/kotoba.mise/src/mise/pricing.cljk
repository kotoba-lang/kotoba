(ns mise.pricing
  "Price + totals math (pure). A Price is {:amount <number> :currency \"JPY\"}.

  All amounts are plain numbers in the smallest currency unit convention is the
  host's choice; mise keeps them as numbers and rounds tax to the nearest whole
  unit via the injected rounding fn (default clojure.core/round). Tax is a
  simple rate (0.08 = 8%). Discounts are an injected IDiscount port (stub).

  Portable .cljc, zero host effects."
  (:require [kotoba.lang.text :as str]))

(defrecord Price [amount currency])

(defn price
  "Construct a Price. amount is a number; currency defaults to \"JPY\"."
  ([amount]
   (price amount "JPY"))
  ([amount currency]
   (->Price amount currency)))

(defn price?
  [x] (and (map? x) (number? (:amount x)) (:currency x)))

(defn zero-price
  ([]
   (zero-price "JPY"))
  ([currency]
   (->Price 0 currency)))

(defn add
  "Add two prices (must share currency). Returns a Price."
  [a b]
  (cond
    (nil? a) b
    (nil? b) a
    :else
    (let [cur (:currency a (:currency b "JPY"))]
      (when (not= (:currency a) (:currency b))
        (throw (ex-info "currency mismatch"
                        {:a a :b b})))
      (->Price (+ (:amount a 0) (:amount b 0)) cur))))

(defn multiply
  "Multiply a price by a scalar (e.g. qty). Returns a Price.

  **nil means \"no price\", which multiplies to zero.** `cart/net-total`
  depends on this: with no discount applied it evaluates
  `(multiply nil -1)` and needs a zero back rather than an exception.

  A price that is *present but malformed* (a map whose `:amount` is not a
  number) is a different thing and throws — absent and corrupt should not
  produce the same answer."
  [p n]
  (when (and (some? p) (not (number? (:amount p))))
    (throw (ex-info "malformed price: :amount is not a number" {:price p})))
  (->Price (* (:amount p 0) (or n 0)) (:currency p "JPY")))

(defn line-total
  "unit-price × qty for a cart/order line.

  **Unlike `multiply`, a nil unit-price is an error here, not a zero.**
  A line item always has a price; when one is missing the old behaviour
  silently produced ¥0 and the row rendered as free — a pricing error that
  looks exactly like a legitimately free item and is only noticed after
  the money has moved. Failing here is the cheapest place to catch it."
  [unit-price qty]
  (when-not (number? (:amount unit-price))
    (throw (ex-info "line-total requires a unit price"
                    {:unit-price unit-price :qty qty})))
  (multiply unit-price qty))

;; ---------------------------------------------------------------------------
;; protocol ports (injected adapters)
;; ---------------------------------------------------------------------------

(defprotocol IDiscount
  (apply-discount [this ctx subtotal]
    "Return a Price representing the discount amount subtracted from subtotal.
    ctx is an opaque map the adapter may inspect (cart/checkout). Implementations
    must be pure functions of (ctx, subtotal)."))

(defrecord NoDiscount []
  IDiscount (apply-discount [_ _ _] (zero-price)))

(defn no-discount [] (->NoDiscount))

;; ---------------------------------------------------------------------------
;; volume/tiered discount (qty-break pricing) — a concrete IDiscount adapter
;; ---------------------------------------------------------------------------

(defrecord VolumeDiscount [tiers]
  ;; tiers is a sorted (desc by qty) seq of [min-qty discount-fraction], e.g.
  ;; [[10 0.10] [5 0.05] [1 0.0]] — buy ≥10 get 10% off, ≥5 get 5%, else 0.
  ;; The discount applies to the whole line based on its qty.
  IDiscount
  (apply-discount [_ ctx subtotal]
    (let [qty (get ctx :qty (get ctx :total-qty 0))]
      (if-let [tier (some (fn [[min-q _]] (when (>= qty min-q) min-q)) tiers)]
        (let [frac (some (fn [[min-q f]] (when (= min-q tier) f)) tiers)]
          (->Price (* (:amount subtotal 0) frac) (:currency subtotal "JPY")))
        (zero-price)))))

(defn volume-discount
  "Build a VolumeDiscount from a tiers map {min-qty → fraction}. Returns a
  discount adapter whose fraction is the highest tier the qty reaches."
  [tiers-map]
  (let [tiers (sort-by first > (seq tiers-map))]        ; desc by min-qty
    (->VolumeDiscount tiers)))

(defrecord BundleDiscount [bundle-qty bundle-fraction]
  ;; Buy N of qualifying items, get bundle-fraction off. ctx carries :bundle-qty.
  IDiscount
  (apply-discount [_ ctx subtotal]
    (let [q (get ctx :bundle-qty 0)]
      (if (>= q bundle-qty)
        (->Price (* (:amount subtotal 0) bundle-fraction) (:currency subtotal "JPY"))
        (zero-price)))))

(defn bundle-discount [bundle-qty fraction] (->BundleDiscount bundle-qty fraction))

(defprotocol ITax
  (compute-tax [this ctx subtotal]
    "Return a Price representing the tax on subtotal. ctx may carry :rate or
    shipping address. Pure."))

(defrecord FlatTax [rate]
  ITax (compute-tax [_ _ subtotal]
        (->Price #?(:clj (Math/round (double (* (:amount subtotal 0) (or rate 0))))
                    :cljs (js/Math.round (* (:amount subtotal 0) (or rate 0))))
                  (:currency subtotal "JPY"))))

(defn flat-tax
  "Simple flat-rate tax adapter (rate is a fraction, 0.08 = 8%)."
  ([rate] (->FlatTax rate)))

(defprotocol IShipping
  (compute-shipping [this ctx subtotal]
    "Return a Price for shipping given ctx + subtotal. Pure."))

(defrecord FreeShipping []
  IShipping (compute-shipping [_ _ _] (zero-price)))

(defn free-shipping [] (->FreeShipping))

;; ---------------------------------------------------------------------------
;; totals
;; ---------------------------------------------------------------------------

(defn subtotal
  "Sum of line totals. lines is a seq of {:unit-price :qty} (or :price/:qty)."
  [lines]
  (reduce add (zero-price)
          (map (fn [l]
                 (line-total (or (:unit-price l) (:price l)) (or (:qty l) 0)))
               lines)))

(defn totals
  "Compute {:subtotal :discount :tax :shipping :total} for a cart's lines.
  Adapters: :discount IDiscount, :tax ITax, :shipping IShipping, :ctx opaque."
  [lines {:keys [discount tax shipping ctx] :or {discount (no-discount)
                                                 tax (flat-tax 0.0)
                                                 shipping (free-shipping)}}]
  (let [sub (subtotal lines)
        disc (apply-discount discount (or ctx {}) sub)
        after-disc (add sub (multiply disc -1))
        tax-amt (compute-tax tax (or ctx {}) after-disc)
        ship-amt (compute-shipping shipping (or ctx {}) after-disc)
        total (add (add after-disc tax-amt) ship-amt)]
    {:subtotal sub
     :discount disc
     :tax tax-amt
     :shipping ship-amt
     :total total}))

(defn- group-digits
  "Insert thousands separators into the decimal string of a non-negative number.
  Portable (no java.text). 12800 -> \"12,800\"."
  [n]
  (let [s (str (long (max 0 (or n 0))))]
    (->> (reverse s)
         (partition 3 3 nil)
         (map (comp #(apply str %) reverse)) ; un-reverse each group's chars
         reverse                              ; restore group order
         (str/join ","))))

(defn- currency-prefix [currency]
  (get {:JPY "¥" :USD "$" :EUR "€"} (keyword currency)
       (str currency " ")))

(defn format-price
  "Render a Price as a human string, e.g. \"¥12,800\". Currency prefix map is
  extensible; default JPY uses ¥ and no decimals. Portable (no java.text)."
  ([p]
   (format-price p nil))
  ([{:keys [amount currency] :or {currency "JPY" amount 0}} opts]
   (str (currency-prefix currency) (group-digits (or amount 0)))))
