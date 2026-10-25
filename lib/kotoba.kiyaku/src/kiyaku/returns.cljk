(ns kiyaku.returns
  "Returns / RMA model (pure). ReturnRequest{:id :order-id :account-id :items
  :reason :status :refund-amount}. Status: :requested → :approved → :shipped →
  :received → :refunded (| :rejected from requested/approved). Items are
  [{:sku :qty :reason}]. Projects to chobo.ledger lane :returns."
  (:require [chobo.ledger :as ledger]))

(defrecord ReturnRequest [id order-id account-id items reason status refund-amount created-at])

(def statuses #{:requested :approved :shipped :received :refunded :rejected})
(def transitions
  {:requested #{:approved :rejected}
   :approved  #{:shipped :rejected}
   :shipped   #{:received}
   :received  #{:refunded}
   :refunded  #{}
   :rejected  #{}})

(defn return-request [m] (merge {:status :requested :items [] :reason :other} m))

(defn can-transition? [from to] (contains? (get transitions from #{}) to))
(defn transition [r to] (when (can-transition? (:status r :requested) to) (assoc r :status to)))

(defn approve [r] (transition r :approved))
(defn reject [r] (transition r :rejected))
(defn mark-shipped [r] (transition r :shipped))
(defn mark-received [r] (transition r :received))
(defn refund
  "Mark a :received return as :refunded with a refund amount. Returns nil if
  the return is not at :received."
  [r amount]
  (when (can-transition? (:status r :requested) :refunded)
    (-> r (assoc :status :refunded) (assoc :refund-amount amount))))
(defn set-refund [r] (transition r :refunded))

(defn total-return-qty [r] (reduce + 0 (map :qty (:items r []))))

;; ---------------------------------------------------------------------------
;; line-item refund computation + restock flag
;; ---------------------------------------------------------------------------

(defn line-refund-amount
  "Compute the refund for a single return line: unit-price × qty (clamped at 0).
  The line may carry :unit-price directly, or the caller passes a price-lookup
  fn (fn [sku] → Price) as the second arg."
  ([line]
   (let [unit (:unit-price line (:price line 0))
         qty (:qty line 1)]
     (max 0 (* (or unit 0) (or qty 0)))))
  ([price-lookup line]
   (let [unit (or (:unit-price line) (:amount (price-lookup (:sku line)) 0))
         qty (:qty line 1)]
     (max 0 (* (or unit 0) (or qty 0))))))

(defn total-refund-amount
  "Sum line refunds across all return items. price-lookup optional."
  ([r]
   (reduce + 0 (map line-refund-amount (:items r []))))
  ([r price-lookup]
   (reduce + 0 (map #(line-refund-amount price-lookup %) (:items r [])))))

(defn restock-items
  "Extract the items eligible for restocking (those not flagged :damaged or
  :final-sale). Returns [{:sku :qty}]."
  [r]
  (->> (:items r [])
       (filter #(not (or (:damaged %) (:final-sale %))))
       (map #(select-keys % [:sku :qty]))
       (filterv #(pos? (:qty % 0)))))

(defn refund-with-restock
  "Mark a :received return as :refunded, computing the refund from line items
  (price-lookup optional) and attaching a :restock-items list. Returns nil if
  the return is not at :received."
  ([r]
   (refund-with-restock r nil))
  ([r price-lookup]
   (when (can-transition? (:status r :requested) :refunded)
     (let [amount (if price-lookup
                    (total-refund-amount r price-lookup)
                    (total-refund-amount r))]
       (-> r
           (assoc :status :refunded :refund-amount amount)
           (assoc :restock-items (restock-items r)))))))

(defn return-activity
  "Project a return event onto chobo.ledger as a :returns activity."
  [r opts]
  (ledger/activity
   (merge {:lane :returns :kind :rma
           :title (str "RMA " (:id r)) :state (:status r :requested)
           :props {:return-id (:id r) :order-id (:order-id r)
                   :account-id (:account-id r) :items (:items r)
                   :refund-amount (:refund-amount r 0)}}
          opts)))
