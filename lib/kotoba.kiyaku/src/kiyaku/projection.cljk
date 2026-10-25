(ns kiyaku.projection
  "Cross-domain projection: mise.order → kiyaku return eligibility.

  Bridges retail EC (mise) and customer/returns (kiyaku): given a mise order,
  compute return eligibility (within return window, not already returned) and
  build a draft ReturnRequest from selected line items. v1 is pure — the host
  app owns the order store and return policy config."
  (:require [kiyaku.returns :as returns]
            [chobo.ledger :as ledger]))

(defn within-return-window?
  "True if the order is still within its return window. v1 stub policy: an
  order with a :created-at is returnable while now ≤ return-deadline (or, with
  no explicit deadline, any time — the host app supplies the real window-days
  policy and sets :return-deadline)."
  ([ord now]
   (within-return-window? ord now 30))
  ([ord now window-days]
   (let [deadline (:return-deadline ord)
         created (:created-at ord)]
     (cond
       deadline (not (pos? (compare (str now) (str deadline)))) ; now ≤ deadline
       created true   ; v1 stub: has a created-at → eligible (host sets deadline)
       :else true))))

(defn return-eligible?
  "True if the order may be returned: within window and not already returned.
  `prior-returns` is a seq of ReturnRequests for this order (status not
  :rejected)."
  [ord now prior-returns]
  (and (within-return-window? ord now)
       (not (some #(and (= (:order-id %) (:id ord))
                        (not= (:status %) :rejected))
                  prior-returns))))

(defn draft-return
  "Build a draft ReturnRequest for selected order lines. `lines` is a seq of
  {:sku :qty :reason}. Returns a ReturnRequest at :requested."
  [ord account-id lines]
  (returns/return-request
   {:order-id (:id ord)
    :account-id account-id
    :items (vec lines)
    :reason (:reason (first lines) :other)}))

(defn return-eligibility-activity
  "Project the eligibility check onto chobo.ledger as a :returns activity
  (kind :eligibility-check). Caller appends."
  [ord eligible? opts]
  (ledger/activity
   (merge {:lane :returns :kind :eligibility-check
           :title (str "Return eligibility for order " (:id ord))
           :props {:order-id (:id ord) :eligible eligible?}}
          opts)))
