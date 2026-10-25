(ns game.economy-operations
  "Provider-neutral economy operations and risk controls.

  The host verifies payment-provider events, authenticates operators and persists
  the ledger. This pure layer owns anomaly signals, reconciliation, dual-control
  adjustments, chargeback debt and append-only audit invariants.")

(def contract-version 1)
(def currencies #{:free-gem :paid-gem})
(def event-kinds #{:settlement :purchase :gift :reward :refund :chargeback :compensation :correction})
(def adjustment-kinds #{:refund :chargeback :compensation :correction})
(def risk-actions #{:allow :review :block})

(def default-policy
  {:velocity/window-ms 60000 :velocity/max-events 10
   :amount/review 1000 :amount/block 10000
   :dual-control/amount 500 :debt/hold-capabilities #{:store :gift}})

(defn operations-state []
  {:economy-ops/version contract-version :events {} :provider-refs {}
   :risk-alerts {} :holds {} :adjustments {} :debts {} :audit []})

(defn- audit [state id actor action target at data]
  (if (some #(= id (:audit/id %)) (:audit state)) state
    (update state :audit conj #:audit{:id id :actor actor :action action
                                      :target target :at at :data data})))

(defn valid-event? [{:economy-event/keys [id player kind currency amount at provider-ref verified?]}]
  (and id player (contains? event-kinds kind) (contains? currencies currency)
       (integer? amount) (not (zero? amount)) (integer? at)
       (or (nil? provider-ref) (string? provider-ref)) (boolean? verified?)))

(defn- recent-player-events [state player at window]
  (filter #(and (= player (:economy-event/player %))
                (<= (- at window) (:economy-event/at %) at))
          (vals (:events state))))

(defn assess-event
  "Record one verified/unverified economy event and return a deterministic risk
  decision. IDs are retry keys. Provider references may identify only one event."
  ([state event] (assess-event state default-policy event))
  ([state policy {:economy-event/keys [id player amount at provider-ref verified?] :as event}]
   (cond
     (not (valid-event? event)) [:error :invalid-event state]
     (contains? (:events state) id) [:duplicate (get-in state [:events id :economy-event/decision]) state]
     :else
     (let [prior-ref (and provider-ref (get-in state [:provider-refs provider-ref]))
           velocity (count (recent-player-events state player at (:velocity/window-ms policy)))
           signals (cond-> []
                     (not verified?) (conj {:signal :unverified :score 100})
                     (and prior-ref (not= prior-ref id)) (conj {:signal :provider-ref-reuse :score 100})
                     (>= velocity (:velocity/max-events policy)) (conj {:signal :velocity :score 50 :observed (inc velocity)})
                     (>= (abs amount) (:amount/review policy)) (conj {:signal :high-amount :score 40 :observed (abs amount)}))
           score (reduce + (map :score signals))
           action (cond (or (not verified?) prior-ref (>= (abs amount) (:amount/block policy))) :block
                        (>= score 40) :review :else :allow)
           decision {:risk/action action :risk/score score :risk/signals signals}
           recorded (assoc event :economy-event/decision decision)
           next (cond-> (assoc-in state [:events id] recorded)
                  provider-ref (assoc-in [:provider-refs provider-ref] id)
                  (not= action :allow) (assoc-in [:risk-alerts id]
                                                 #:risk{:id id :player player :action action
                                                        :score score :signals signals :at at :status :open}))]
       [:ok decision next]))))

(defn reconcile-wallet
  "Compare a materialized balance to the immutable ledger. Opening balance is
  explicit; no caller may hide a drift by choosing a convenient start value."
  [opening-balance transactions materialized-balance]
  (if (or (not (integer? opening-balance)) (neg? opening-balance)
          (not (integer? materialized-balance)) (not (sequential? transactions))
          (not-every? #(integer? (:amount %)) transactions))
    {:reconciliation/status :invalid}
    (let [expected (+ opening-balance (reduce + 0 (map :amount transactions)))
          drift (- materialized-balance expected)]
      {:reconciliation/status (if (zero? drift) :balanced :drift)
       :reconciliation/expected expected :reconciliation/actual materialized-balance
       :reconciliation/drift drift})))

(defn request-adjustment
  [state policy {:adjustment/keys [id player kind currency amount source-ref reason requested-by
                                   requested-at] :as adjustment}]
  (cond
    (or (nil? id) (nil? player) (not (contains? adjustment-kinds kind))
        (not (contains? currencies currency)) (not (integer? amount)) (zero? amount)
        (and (contains? #{:refund :chargeback} kind) (pos? amount))
        (and (= :compensation kind) (neg? amount))
        (nil? source-ref) (or (not (string? reason)) (empty? reason) (> (count reason) 1000))
        (nil? requested-by) (not (integer? requested-at)))
    [:error :invalid-adjustment state]
    (contains? (:adjustments state) id) [:duplicate (get-in state [:adjustments id]) state]
    :else
    (let [required (if (>= (abs amount) (:dual-control/amount policy)) 2 1)
          record (assoc adjustment :adjustment/status :pending :adjustment/approvals #{}
                                   :adjustment/required-approvals required)
          next (-> state (assoc-in [:adjustments id] record)
                   (audit (str "audit:" id) requested-by :adjustment-requested id requested-at
                          {:kind kind :amount amount :required-approvals required}))]
      [:ok record next])))

(defn approve-adjustment [state adjustment-id approver at audit-id]
  (let [record (get-in state [:adjustments adjustment-id])]
    (cond
      (nil? record) [:error :adjustment-not-found state]
      (not= :pending (:adjustment/status record)) [:duplicate record state]
      (= approver (:adjustment/requested-by record)) [:error :requester-cannot-approve state]
      (contains? (:adjustment/approvals record) approver) [:duplicate record state]
      :else
      (let [approvals (conj (:adjustment/approvals record) approver)
            status (if (>= (count approvals) (:adjustment/required-approvals record)) :approved :pending)
            next (-> state
                     (assoc-in [:adjustments adjustment-id :adjustment/approvals] approvals)
                     (assoc-in [:adjustments adjustment-id :adjustment/status] status)
                     (audit audit-id approver :adjustment-approved adjustment-id at
                            {:approval-count (count approvals) :status status}))]
        [:ok (get-in next [:adjustments adjustment-id]) next]))))

(defn apply-adjustment
  "Apply an approved adjustment to a balance. Chargebacks/refunds that exceed
  available gems set balance to zero and record enforceable debt instead of
  silently dropping the provider event."
  [state policy adjustment-id balance applied-at actor audit-id]
  (let [record (get-in state [:adjustments adjustment-id])]
    (cond
      (nil? record) [:error :adjustment-not-found state]
      (= :applied (:adjustment/status record)) [:duplicate record state]
      (not= :approved (:adjustment/status record)) [:error :adjustment-not-approved state]
      (or (not (integer? balance)) (neg? balance)) [:error :invalid-balance state]
      :else
      (let [amount (:adjustment/amount record)
            raw (+ balance amount)
            debt (max 0 (- raw))
            next-balance (max 0 raw)
            player (:adjustment/player record)
            applied (assoc record :adjustment/status :applied :adjustment/applied-at applied-at
                                  :adjustment/applied-by actor :adjustment/debt-created debt)
            next (-> state (assoc-in [:adjustments adjustment-id] applied)
                     (cond-> (pos? debt)
                       (update-in [:debts player] (fnil + 0) debt)
                       (pos? debt)
                       (assoc-in [:holds player]
                                 {:hold/reason :economy-debt
                                  :hold/capabilities (:debt/hold-capabilities policy)
                                  :hold/at applied-at}))
                     (audit audit-id actor :adjustment-applied adjustment-id applied-at
                            {:amount amount :balance-before balance :balance-after next-balance
                             :debt-created debt}))]
        [:ok {:balance next-balance :debt debt :transaction
              {:id (str "adjustment:" adjustment-id) :currency (:adjustment/currency record)
               :amount (- next-balance balance) :kind (:adjustment/kind record)
               :ref (:adjustment/source-ref record)
               :at applied-at}} next]))))

(defn repay-debt [state player amount at actor audit-id]
  (let [debt (get-in state [:debts player] 0)]
    (cond
      (or (not (integer? amount)) (not (pos? amount))) [:error :invalid-repayment state]
      (zero? debt) [:duplicate state]
      :else (let [remaining (max 0 (- debt amount))
                  next (-> state (assoc-in [:debts player] remaining)
                           (cond-> (zero? remaining) (update :holds dissoc player))
                           (audit audit-id actor :debt-repaid player at
                                  {:amount (min debt amount) :remaining remaining}))]
              [:ok remaining next]))))
