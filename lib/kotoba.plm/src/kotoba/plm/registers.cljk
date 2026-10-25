(ns kotoba.plm.registers
  "Two inventory registers: what we OWN and what we HOLD.

   Valueflows keeps `accountingQuantity` and `onhandQuantity` apart, and the
   reason is not pedantry — it is the difference between these three, which a
   single register cannot tell apart:

     transfer            ownership and custody both move
     transferAllRights   ownership moves, the goods do not (title sale, sale
                         in transit, drop-ship)
     transferCustody     the goods move, ownership does not (consignment
                         stock, subcontract material at a supplier, bonded
                         warehouse)

   Until this namespace, `kotoba.plm` had one column, `:erp.inventory/qty-on-hand`,
   so consignment stock either inflated what the company owned or vanished from
   what it physically held. Neither is a rounding problem: one overstates the
   balance sheet and the other tells MRP to buy material that is already in
   the building.

   WHICH REGISTER MOVES IS NOT DECIDED HERE. It comes from the pinned
   Valueflows action behaviour table (`ws-valueflo-vocabulary`), so `produce`
   increments both and `transferCustody` increments only onhand because the
   specification says so. Re-deriving that table in a second place is how one
   copy gets fixed and the other does not.

   NETTING USES ONHAND. `mrp/plan` nets gross requirements against what can
   actually be consumed, which is custody, not title. Consignment material
   sitting on our floor is available to a work order; goods we own but that
   are still on a ship are not."
  (:require [valueflows.vocabulary :as vocab]
            [kotoba.plm.db :as db]))

(def onhand-attr :erp.inventory/qty-on-hand)
(def accounting-attr :erp.inventory/qty-accounting)

;; ── reading ───────────────────────────────────────────────────────────────
;; nil means NOT RECORDED, which is not zero. A row written before this
;; namespace existed has no accounting quantity, and answering 0 for it would
;; report a company that owns nothing.

(defn onhand
  "Physical custody, or nil when the row has none recorded."
  [d inv-id]
  (db/attr d onhand-attr [:erp.inventory/id inv-id]))

(defn accounting
  "Ownership, or nil when not recorded. Rows created before the second
   register existed return nil here — see `accounting-or-onhand`."
  [d inv-id]
  (db/attr d accounting-attr [:erp.inventory/id inv-id]))

(defn accounting-or-onhand
  "Ownership, falling back to custody for rows written before the second
   register existed, WITH the fallback reported:

     {:value 12M :source :accounting}   ; recorded
     {:value 12M :source :onhand-fallback}
     {:value nil :source :unrecorded}

   A bare number here would make a legacy row indistinguishable from one whose
   two registers happen to be equal, and those are different facts."
  [d inv-id]
  (if-let [a (accounting d inv-id)]
    {:value a :source :accounting}
    (if-let [o (onhand d inv-id)]
      {:value o :source :onhand-fallback}
      {:value nil :source :unrecorded})))

(defn available
  "The netting basis for MRP: what can be consumed. Custody, not title."
  [d inv-id]
  (or (onhand d inv-id) 0M))

;; ── which registers an action moves ───────────────────────────────────────

(def ^:private one-sided
  "A single company's books hold one side of a two-sided flow. `:receiver`
   applies the increment half of a decrementIncrement, `:provider` the
   decrement half. `:both` is for a movement inside one set of books."
  #{:provider :receiver :both})

(defn effects
  "=> {:onhand :increment|:decrement|nil :accounting …} for `action` seen from
   `side`. nil means that register does not move.

   Derived from the vocabulary, never hardcoded."
  [action side]
  {:pre [(contains? one-sided side)]}
  (letfn [(half [e]
            (case e
              :increment :increment
              :decrement :decrement
              :incrementTo (when (#{:receiver :both} side) :increment)
              :decrementIncrement (case side
                                    :receiver :increment
                                    :provider :decrement
                                    :both nil)   ; nets to zero in one book
              nil))]
    {:onhand (half (vocab/effect action :onhand-effect))
     :accounting (half (vocab/effect action :accounting-effect))}))

(defn- apply-delta [current effect qty]
  (case effect
    :increment (+ (or current 0M) qty)
    :decrement (- (or current 0M) qty)
    nil))

(defn posting
  "The inventory tx map for `action` x `qty` against one row, moving whichever
   registers the vocabulary says it moves.

   => {:ok? true :tx {…}} | {:ok? false :error {…}}

   Refuses an unknown action and a non-positive quantity rather than posting
   nothing and reporting success."
  [d inv-id action qty {:keys [side] :or {side :both}}]
  (cond
    (not (vocab/action? action))
    {:ok? false :error {:code :unknown-action :action action
                        :known (vocab/action-names)}}

    (not (and (number? qty) (pos? qty)))
    {:ok? false :error {:code :quantity-not-positive :quantity qty}}

    :else
    (let [e (effects action side)
          o (apply-delta (onhand d inv-id) (:onhand e) qty)
          a (apply-delta (accounting d inv-id) (:accounting e) qty)]
      (if (and (nil? o) (nil? a))
        {:ok? false :error {:code :action-moves-no-register :action action :side side
                            :effects e
                            :why "posting it would change nothing while reporting success"}}
        {:ok? true
         :effects e
         :tx (cond-> {:erp.inventory/id inv-id}
               (some? o) (assoc onhand-attr o)
               (some? a) (assoc accounting-attr a))}))))

(defn divergence
  "Rows where ownership and custody disagree — consignment in, title sold and
   not yet shipped, material at a subcontractor. The report a single-register
   system could not produce at all.

   `inv-ids` is explicit: this namespace does not scan, because a scan over an
   unknown set would report 'no divergence' for rows it never looked at."
  [d inv-ids]
  (let [rows (for [id inv-ids
                   :let [o (onhand d id)
                         a (accounting d id)]
                   :when (not= o a)]
               {:inventory id :onhand o :accounting a
                :kind (cond
                        (nil? a) :accounting-unrecorded
                        (nil? o) :onhand-unrecorded
                        (> a o) :owned-not-held
                        :else :held-not-owned)})]
    {:scanned (count inv-ids)
     :diverged (count rows)
     :rows (vec rows)
     :empty-input? (zero? (count inv-ids))}))
