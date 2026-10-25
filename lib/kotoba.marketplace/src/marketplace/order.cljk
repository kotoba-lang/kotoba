(ns marketplace.order
  "The multi-seller order — the contract that ties listing, settlement,
  fulfillment and delivery into one thing a buyer recognises.

  ## Why this exists

  `kotoba.okaimono` already models an order beautifully: line items,
  totals, a COD flag, and an explicit status-transition table. But its
  order belongs to ONE store. A marketplace basket does not: its lines
  belong to different sellers, who pick, pack and ship independently and
  may deliver days apart.

  So a marketplace order is modelled as a PARENT over per-seller
  `okaimono` sub-orders — one sub-order per seller, each a genuine
  `okaimono` record that the courier and warehouse actors can consume
  unchanged. The parent owns only what is genuinely shared: the buyer,
  the currency, and the derived overall status.

  ## Status is derived, never asserted

  `overall-status` is COMPUTED from the sub-orders every time. There is
  deliberately no setter. A parent that stored its own status could
  disagree with its parts — a buyer told 'delivered' while one seller's
  parcel is still in a depot — and that disagreement is exactly the bug
  a marketplace cannot afford. The rule is conservative: an order is
  only `:delivered` when EVERY sub-order is, and any sub-order still
  moving keeps the whole order in flight.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [kotoba.okaimono :as ok]))

;; ───────────────────────────── construction ─────────────────────────────

(defn sub-order-id
  "Deterministic sub-order id: one per (order, seller)."
  [order-id seller]
  (str order-id ".s." seller))

(defn order
  "Build a multi-seller order from lines that each name a `:seller`.

  Each line is `{:seller .. :offer .. :sku .. :name .. :qty ..
  :unit-price-minor ..}`. Lines are grouped by seller into `okaimono`
  sub-orders, seller-sorted so the same basket always produces the same
  structure.

  Returns nil when any line is unusable — `kotoba.okaimono/line` is the
  arbiter of that, so quantity/price validation lives in one place
  rather than being re-implemented here."
  [{:keys [id buyer lines currency cod?]
    :or   {currency "JPY" cod? false}}]
  (let [groups (->> lines (group-by :seller) (sort-by key))
        subs   (for [[seller ls] groups
                     :let [ok-lines (mapv #(ok/line (:sku %) (:name %)
                                                    (:qty %) (:unit-price-minor %))
                                          ls)]]
                 (when (every? some? ok-lines)
                   (ok/order (sub-order-id id seller) seller buyer ok-lines
                             :currency currency :cod? cod?)))]
    (when (and (seq groups) (every? some? subs))
      {:order/id         id
       :order/buyer      buyer
       :order/currency   currency
       :order/cod?       (boolean cod?)
       :order/sub-orders (vec subs)
       :order/sellers    (mapv first groups)})))

(defn sub-order
  "The sub-order for one seller, or nil."
  [o seller]
  (first (filter #(= seller (:okaimono/store %)) (:order/sub-orders o))))

;; ───────────────────────────── money ─────────────────────────────

(defn total-minor
  "Order total: the sum of every sub-order's own total. Delegates to
  `kotoba.okaimono/total` so the arithmetic is defined once."
  [o]
  (reduce + 0 (map ok/total (:order/sub-orders o))))

(defn seller-subtotal-minor
  [o seller]
  (some-> (sub-order o seller) ok/total))

(defn ->basket-lines
  "Project the order into `marketplace.settlement` basket lines.

  This is the seam between the order and the money: settlement never
  reads an order, it reads basket lines, so the two can be tested
  independently and an order shape change cannot silently alter a
  payout."
  [o]
  (mapv (fn [s] {:line/seller       (:okaimono/store s)
                 :line/offer        (sub-order-id (:order/id o) (:okaimono/store s))
                 :line/amount-minor (ok/total s)
                 :line/qty          (ok/item-count s)})
        (:order/sub-orders o)))

;; ───────────────────────────── status ─────────────────────────────

(def ^:private rank
  "How far along a sub-order is. Used only to find the LEAST advanced
  sub-order — the parent can never be ahead of its slowest part."
  {:placed 0 :confirmed 1 :packed 2 :handed-over 3 :delivered 4})

(defn overall-status
  "Derive the order's status from its sub-orders. Never stored.

    - every sub-order :cancelled            -> :cancelled
    - every sub-order :delivered            -> :delivered
    - some delivered, some not              -> :partially-delivered
    - otherwise                             -> the LEAST advanced
                                               non-cancelled sub-order's
                                               status

  A cancelled sub-order among live ones does not cancel the order; the
  buyer still has the rest coming, and reporting `:cancelled` there
  would be a lie the refund logic would then have to work around."
  [o]
  (let [ss     (map :okaimono/status (:order/sub-orders o))
        live   (remove #{:cancelled} ss)]
    (cond
      (empty? ss)                      nil
      (every? #{:cancelled} ss)        :cancelled
      (every? #{:delivered} live)      (if (some #{:cancelled} ss)
                                         :partially-delivered
                                         :delivered)
      (some #{:delivered} live)        :partially-delivered
      :else                            (->> live
                                            (sort-by #(get rank % 0))
                                            first))))

(defn fully-delivered?
  "The single question settlement asks before an escrow may release:
  is EVERY seller's parcel delivered?

  `:partially-delivered` deliberately answers false. Releasing every
  seller's money because one of them delivered is precisely the
  multi-seller failure this contract exists to prevent."
  [o]
  (= :delivered (overall-status o)))

(defn seller-delivered?
  "Whether ONE seller's sub-order is delivered — the per-seller release
  question, for operators who settle each seller independently rather
  than waiting for the whole order."
  [o seller]
  (boolean (some-> (sub-order o seller) ok/delivered?)))

;; ───────────────────────────── transitions ─────────────────────────────

(defn advance-sub-order
  "Advance ONE seller's sub-order, delegating the legality of the
  transition to `kotoba.okaimono/advance`. Returns nil when the
  transition is not allowed (a refusal, not an exception) or the seller
  is unknown — so an illegal move can never be half-applied to the
  parent."
  [o seller to]
  (when-let [s (sub-order o seller)]
    (when-let [advanced (ok/advance s to)]
      (assoc o :order/sub-orders
             (mapv #(if (= seller (:okaimono/store %)) advanced %)
                   (:order/sub-orders o))))))

(defn dispatchable-sellers
  "Sellers whose sub-order a courier may collect right now. Delegates to
  `kotoba.okaimono/dispatchable?` — the courier actor
  (`cloud-itonami-isic-5320`) asks exactly this question, so the answer
  must come from the same function it already uses."
  [o]
  (->> (:order/sub-orders o)
       (filter ok/dispatchable?)
       (mapv :okaimono/store)))

;; ───────────────────────────── validation ─────────────────────────────

(defn order-errors
  "Structural errors, `[]` when sound."
  [o]
  (vec
   (concat
    (when (str/blank? (str (:order/id o)))
      [{:order.error/code :missing-id}])
    (when (str/blank? (str (:order/buyer o)))
      [{:order.error/code :missing-buyer}])
    (when (empty? (:order/sub-orders o))
      [{:order.error/code :no-sub-orders}])
    (when-not (and (string? (:order/currency o))
                   (re-matches #"^[A-Z]{3}$" (str (:order/currency o))))
      [{:order.error/code :invalid-currency}])
    ;; Every sub-order must itself be a valid okaimono record — the
    ;; parent is not allowed to be sound while a part is not.
    (for [s (:order/sub-orders o)
          :let [v (ok/validate-order s)]
          :when (not (:okaimono/valid? v))]
      {:order.error/code :invalid-sub-order
       :order.error/detail (str (:okaimono/store s) ": " (:okaimono/error v))})
    ;; One sub-order per seller: two would split a seller's money across
    ;; two settlement allocations and double their fixed costs.
    (let [sellers (map :okaimono/store (:order/sub-orders o))]
      (when (not= (count sellers) (count (set sellers)))
        [{:order.error/code :duplicate-seller-sub-order}]))
    (when (some #(not= (:order/currency o) (:okaimono/currency %))
                (:order/sub-orders o))
      [{:order.error/code :mixed-currency
        :order.error/detail "親注文と子注文の通貨が一致しない"}]))))

(defn valid-order? [o] (empty? (order-errors o)))
