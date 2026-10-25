(ns game.subscription
  "Provider-neutral subscription and membership lifecycle.

  Hosts authenticate payment-provider events and persist grants. This pure CLJC
  layer owns ordering, idempotency, grace periods, cancellation-at-period-end,
  refund/revocation and entitlement projection without trusting a browser clock.")

(def contract-version 1)
(def event-kinds #{:started :renewed :canceled :payment-failed :recovered :refunded :revoked})
(def access-statuses #{:active :grace})

(defn valid-plan?
  [{:plan/keys [id period-ms grace-ms entitlements]}]
  (and (keyword? id) (pos-int? period-ms) (nat-int? grace-ms)
       (set? entitlements) (seq entitlements)
       (every? #(or (keyword? %) (string? %)) entitlements)))

(defn state []
  {:subscription/version contract-version
   :subscriptions {} :events #{} :provider-refs {}})

(defn status
  "Derive access from host time. Cancellation keeps access through the paid
  period; payment failure may enter a bounded grace period. Refund/revocation
  removes access immediately."
  [subscription now]
  (cond
    (nil? subscription) :none
    (:subscription/revoked-at subscription) :revoked
    (:subscription/refunded-at subscription) :refunded
    (< now (:subscription/current-period-end subscription 0)) :active
    (< now (:subscription/grace-end subscription 0)) :grace
    :else :expired))

(defn entitled?
  [s player entitlement now]
  (boolean
   (some #(and (contains? access-statuses (status % now))
               (contains? (:subscription/entitlements %) entitlement))
         (vals (get-in s [:subscriptions player])))))

(defn active-entitlements [s player now]
  (->> (vals (get-in s [:subscriptions player]))
       (filter #(contains? access-statuses (status % now)))
       (mapcat :subscription/entitlements)
       set))

(defn- valid-event?
  [plans {:subscription-event/keys [id player plan kind provider-ref occurred-at
                                    verified? period-end]}]
  (and id player (contains? plans plan) (contains? event-kinds kind)
       (string? provider-ref) (seq provider-ref) (integer? occurred-at)
       (boolean? verified?)
       (if (contains? #{:started :renewed :recovered} kind)
         (and (integer? period-end) (> period-end occurred-at))
         (or (nil? period-end) (integer? period-end)))))

(defn apply-provider-event
  "Apply one already-authenticated provider event. Event IDs make webhook
  retries idempotent; provider references cannot be reused across players or
  plans. Out-of-order events fail closed so an old renewal cannot resurrect a
  refunded membership. Returns [:ok subscription state], [:duplicate ...], or
  [:error reason state]."
  [s plans {:subscription-event/keys [id player plan kind provider-ref occurred-at
                                      period-end] :as event}]
  (let [definition (get plans plan)
        current (get-in s [:subscriptions player plan])
        prior-ref (get-in s [:provider-refs provider-ref])]
    (cond
      (not (valid-event? plans event)) [:error :invalid-event s]
      (not (:subscription-event/verified? event)) [:error :unverified-event s]
      (contains? (:events s) id) [:duplicate current s]
      (and prior-ref (not= prior-ref [player plan])) [:error :provider-ref-reuse s]
      (and current (< occurred-at (:subscription/last-event-at current)))
      [:error :out-of-order-event s]
      (and (contains? #{:renewed :canceled :payment-failed :recovered :refunded :revoked} kind)
           (nil? current)) [:error :subscription-not-found s]
      (and (= kind :started) current (contains? access-statuses (status current occurred-at)))
      [:error :already-active s]
      :else
      (let [base (or current
                     #:subscription{:player player :plan plan :provider-ref provider-ref
                                    :started-at occurred-at
                                    :entitlements (:plan/entitlements definition)})
            next-sub
            (case kind
              :started (assoc base :subscription/current-period-end period-end
                                   :subscription/grace-end period-end
                                   :subscription/canceled-at nil
                                   :subscription/refunded-at nil
                                   :subscription/revoked-at nil)
              :renewed (assoc base :subscription/current-period-end period-end
                                   :subscription/grace-end period-end
                                   :subscription/refunded-at nil
                                   :subscription/revoked-at nil)
              :recovered (assoc base :subscription/current-period-end period-end
                                     :subscription/grace-end period-end)
              :canceled (assoc base :subscription/canceled-at occurred-at)
              :payment-failed (assoc base :subscription/grace-end
                                     (max (:subscription/current-period-end base 0)
                                          (+ occurred-at (:plan/grace-ms definition))))
              :refunded (assoc base :subscription/refunded-at occurred-at
                                    :subscription/grace-end occurred-at)
              :revoked (assoc base :subscription/revoked-at occurred-at
                                   :subscription/grace-end occurred-at))
            recorded (assoc next-sub :subscription/last-event-id id
                                     :subscription/last-event-kind kind
                                     :subscription/last-event-at occurred-at)
            next-state (-> s
                           (assoc-in [:subscriptions player plan] recorded)
                           (update :events conj id)
                           (assoc-in [:provider-refs provider-ref] [player plan]))]
        [:ok recorded next-state]))))

(defn projection [s player now]
  {:subscription/entitlements (active-entitlements s player now)
   :subscription/items
   (->> (vals (get-in s [:subscriptions player]))
        (map #(assoc % :subscription/status (status % now)))
        (sort-by (juxt :subscription/plan :subscription/started-at))
        vec)})
