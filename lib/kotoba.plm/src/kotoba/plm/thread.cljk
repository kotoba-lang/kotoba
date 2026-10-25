(ns kotoba.plm.thread
  "Phase 2/3 — the PLM→ERP reactive thread (ADR-2606171400 §4).

   Each function is one logical commit: it transacts a PLM state change, then
   reads the *released* PLM state back and derives the ERP effect (inventory,
   cost, GL, OCEL). This mirrors the projector `onCommit` of ADR-0025 — in the
   MVP it rides the existing ERP worker instead of a separate projector Worker.

   Released gating is the invariant: only :released items / ECOs produce ERP
   effects; a :draft commit is a reported no-op."
  (:require [kotoba.plm.db :as db]
            [kotoba.plm.item :as plm]
            [kotoba.plm.cost :as cost]
            [kotoba.plm.erp :as erp]))

(defn- inv-id [iid] (str "INV-" iid))

(defn- maybe-supersede!
  "If released item `iid` supersedes a prior item, obsolete that prior revision
   and log an OCEL item.superseded (APQC 2.0 Product/Service). Returns the old id."
  [conn iid]
  (when-let [old (-> (db/pull (db/db conn) [{:plm.item/supersedes [:plm.item/id]}]
                              [:plm.item/id iid])
                     :plm.item/supersedes :plm.item/id)]
    (db/tx! conn [{:plm.item/id old :plm.item/lifecycle :obsolete}
                  (erp/ocel :item.superseded "2.0" [[:plm.item/id iid] [:plm.item/id old]])])
    old))

(defn release-item!
  "item :draft/:in-review → :released, then released-gated derivation:
     :make → register perpetual-inventory row (qty 0) at rolled standard cost
             + cost snapshot + OCEL item.released/inventory.registered/cost.rolledup
     :buy  → procurement-ready, OCEL item.released (APQC 4.0)
   No-op when already released / unknown."
  [conn iid]
  (let [d0 (db/db conn)
        lc (plm/lifecycle d0 iid)
        mb (plm/make-buy d0 iid)]
    (cond
      (nil? lc)        {:ok false :reason :unknown-item :item iid}
      (= lc :released) {:ok false :reason :already-released :item iid}
      :else
      (do
        (db/tx! conn [{:plm.item/id iid
                       :plm.item/lifecycle :released
                       :plm.item/released-at (erp/now)}])
        (let [result
              (if (= mb :make)
                (let [d1      (db/db conn)
                      rolled  (cost/rolled-cost d1 iid nil {:include-process? true})
                      inv-tid "inv"]                    ; tempid links the new inventory row
                  (db/tx! conn
                    [{:db/id                     inv-tid
                      :erp.inventory/id          (inv-id iid)
                      :erp.inventory/item        [:plm.item/id iid]
                      :erp.inventory/qty-on-hand 0M
                      :erp.inventory/qty-accounting 0M
                      :erp.inventory/std-cost    rolled}
                     (erp/cost-snapshot iid rolled)
                     (erp/ocel :item.released        "10.0" [[:plm.item/id iid]])
                     (erp/ocel :inventory.registered "10.0" [inv-tid])
                     (erp/ocel :cost.rolledup        "9.0"  [[:plm.item/id iid]])])
                  {:ok true :item iid :make-buy :make :rolled-cost rolled})
                ;; :buy — register a perpetual-inventory row (qty 0) so MRP can net
                ;; against on-hand and goods can be received against stock.
                (let [std     (or (plm/unit-cost (db/db conn) iid) 0M)
                      inv-tid "inv"]
                  (db/tx! conn
                    [{:db/id                     inv-tid
                      :erp.inventory/id          (inv-id iid)
                      :erp.inventory/item        [:plm.item/id iid]
                      :erp.inventory/qty-on-hand 0M
                      :erp.inventory/qty-accounting 0M
                      :erp.inventory/std-cost    std}
                     (erp/ocel :item.released        "4.0" [[:plm.item/id iid]])
                     (erp/ocel :inventory.registered "4.0" [inv-tid])])
                  {:ok true :item iid :make-buy mb}))
              sup (maybe-supersede! conn iid)]
          (cond-> result sup (assoc :superseded sup)))))))

(defn receive-goods!
  "Goods receipt of `qty` of released make-item `iid` at current standard cost.
   Perpetual inventory: qty↑ and a balanced journal Dr Inventory(1400)/Cr GR-IR(2150)."
  [conn iid qty]
  (let [d (db/db conn)]
    (when-not (plm/released? d iid)
      (throw (ex-info "cannot receive un-released item" {:item iid})))
    (let [qty   (erp/->bigdec qty)
          std   (db/attr d :erp.inventory/std-cost    [:erp.inventory/id (inv-id iid)])
          onh   (or (db/attr d :erp.inventory/qty-on-hand [:erp.inventory/id (inv-id iid)]) 0M)
          acc   (or (db/attr d :erp.inventory/qty-accounting [:erp.inventory/id (inv-id iid)]) onh)
          value (* std qty)
          t     (erp/now)
          jid   (str "JRN-GR-" iid "-" (.getTime t))
          jtid  "jrn"]                                  ; tempid links the new journal
      (db/tx! conn
        ;; A goods receipt under a purchase order moves BOTH registers: we take
        ;; custody and title at once. Consignment receipts do not, which is why
        ;; the two columns exist -- post those through kotoba.plm.registers
        ;; with :transferCustody.
        [{:erp.inventory/id (inv-id iid)
          :erp.inventory/qty-on-hand (+ onh qty)
          :erp.inventory/qty-accounting (+ acc qty)}
         (assoc (erp/journal {:id jid :date t
                              :memo (str "Goods receipt " qty " x " iid " @std " std)
                              :lines [{:account "1400" :debit value :item iid}
                                      {:account "2150" :credit value}]})
                :db/id jtid)
         (erp/ocel :goods.received "10.0" [[:erp.inventory/id (inv-id iid)]])
         (erp/ocel :journal.posted "9.0"  [jtid])])
      {:ok true :item iid :received qty :value value})))

(defn release-eco!
  "ECO :draft → :released. Applies :new-unit-cost to affected :buy items, re-rolls
   every MBOM ancestor that transitively consumes them (direct parents,
   grandparents, and beyond), and posts an inventory-revaluation journal for
   on-hand × Δstandard — design change → standard cost change → P/L variance.
   No-op when already released / unknown."
  [conn eid]
  (let [d0  (db/db conn)
        eco (db/pull d0 [:plm.eco/state :plm.eco/new-unit-cost
                         {:plm.eco/affected [:plm.item/id]}] [:plm.eco/id eid])]
    (cond
      (nil? eco)                          {:ok false :reason :unknown-eco :eco eid}
      (= :released (:plm.eco/state eco))  {:ok false :reason :already-released :eco eid}
      :else
      (let [new-cost (:plm.eco/new-unit-cost eco)
            affected (mapv :plm.item/id (:plm.eco/affected eco))
            ;; revalue the affected buy items' OWN inventory *and* every MBOM
            ;; ancestor that consumes them, transitively (grandparents and
            ;; beyond too, not just direct parents) — a standard change
            ;; ripples all the way up the BOM.
            targets  (->> (concat affected (mapcat #(plm/ancestors-using d0 %) affected))
                          distinct sort vec)]
        ;; (1) release ECO + apply new standard cost to affected buy items
        (db/tx! conn
          (into [{:plm.eco/id eid :plm.eco/state :released :plm.eco/released-at (erp/now)}]
                (for [iid affected]
                  {:plm.item/id iid :plm.item/std-unit-cost new-cost})))
        ;; (2) re-roll each target, revalue on-hand, post variance
        (let [results
              (vec (for [pid targets]
                     (let [d1    (db/db conn)
                           old   (or (db/attr d1 :erp.inventory/std-cost    [:erp.inventory/id (inv-id pid)]) 0M)
                           new   (cost/rolled-cost d1 pid nil {:include-process? true})
                           onh   (or (db/attr d1 :erp.inventory/qty-on-hand [:erp.inventory/id (inv-id pid)]) 0M)
                           reval (* (- new old) onh)
                           t     (erp/now)
                           jid   (str "JRN-RV-" pid "-" (.getTime t))
                           jtid  "jrn"]                  ; tempid links the new journal
                       (db/tx! conn
                         (cond-> [{:erp.inventory/id (inv-id pid) :erp.inventory/std-cost new}
                                  (erp/cost-snapshot pid new)
                                  (erp/ocel :cost.rolledup "9.0" [[:plm.item/id pid]])]
                           (not (zero? reval))
                           (conj (assoc (erp/journal
                                          {:id jid :date t
                                           :memo (str "ECO " eid " revalue " pid " dStd " (- new old) " x on-hand " onh)
                                           :lines (if (pos? reval)
                                                    [{:account "1400" :debit reval :item pid}
                                                     {:account "5900" :credit reval}]
                                                    [{:account "5900" :debit (- reval)}
                                                     {:account "1400" :credit (- reval) :item pid}])})
                                        :db/id jtid)
                                 (erp/ocel :journal.posted "9.0" [jtid]))))
                       {:parent pid :old-std old :new-std new :revaluation reval})))]
          (db/tx! conn [(erp/ocel :eco.released "4.0"
                                  (mapv (fn [iid] [:plm.item/id iid]) affected))])
          {:ok true :eco eid :new-unit-cost new-cost :affected affected :parents results})))))
