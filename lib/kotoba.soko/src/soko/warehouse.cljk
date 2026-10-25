(ns soko.warehouse
  "Warehouse + multi-location stock (pure). Warehouse{:id :name :location :zones}.
  Stock is {sku → {warehouse-id → qty}} (location-aware, vs mise.inventory's
  single {sku→qty}). Transfers move qty between warehouses. Projects to
  chobo.ledger lane :warehouse."
  (:refer-clojure :exclude [available?])
  (:require [chobo.ledger :as ledger]))

(defrecord Warehouse [id name location zones])

(defrecord Stock [levels])

(defn stock [m] (->Stock (or m {})))
(defn stock-from
  "Build stock from a seq of [sku warehouse-id qty]."
  [triples]
  (->Stock
   (reduce (fn [acc [sku wh qty]]
             (assoc-in acc [sku wh] (max 0 qty))) {} triples)))

(defn on-hand
  "Qty of sku at a specific warehouse."
  [st sku wh]
  (get-in st [:levels sku wh] 0))

(defn total-on-hand
  "Total qty of a sku across all warehouses."
  [st sku]
  (reduce + 0 (vals (get-in st [:levels sku] {}))))

(defn available?
  ([st sku wh]
   (available? st sku wh 1))
  ([st sku wh needed]
   (>= (on-hand st sku wh) (max 0 needed))))

(defn adjust
  "Add qty to sku@wh (clamped at 0). Returns new Stock."
  [st sku wh qty]
  (let [cur (on-hand st sku wh)
        new-level (max 0 (+ cur qty))]
    (assoc-in st [:levels sku wh] new-level)))

(defn reserve
  "Decrement sku@wh by qty (clamped at 0)."
  [st sku wh qty]
  (adjust st sku wh (- (max 0 qty))))

(defn restock
  "Increment sku@wh by qty."
  [st sku wh qty]
  (adjust st sku wh (max 0 qty)))

(defn transfer
  "Move qty of sku from wh-from to wh-to (no-op if insufficient). Returns new
  Stock. Does NOT model in-transit (v1 atomic)."
  [st sku wh-from wh-to qty]
  (let [q (max 0 qty)]
    (if (available? st sku wh-from q)
      (-> st (reserve sku wh-from q) (restock sku wh-to q))
      st)))

(defn warehouses-with-sku [st sku]
  (keys (get-in st [:levels sku] {})))

;; ---------------------------------------------------------------------------
;; backorder (negative-effective stock tracking)
;; ---------------------------------------------------------------------------

(defn backorder-qty
  "Shortfall qty for a sku@wh: max(0, needed - on-hand). 0 if sufficient."
  [st sku wh needed]
  (max 0 (- needed (on-hand st sku wh))))

(defn needs-backorder?
  "True if reserving `needed` would exceed on-hand (creates a backorder)."
  [st sku wh needed]
  (pos? (backorder-qty st sku wh needed)))

(defn reserve-or-backorder
  "Reserve what's available (up to on-hand); record the shortfall as backordered.
  Returns {:stock s :backordered qty}. Never clamps stock below 0."
  [st sku wh qty]
  (let [q (max 0 qty)
        avail (on-hand st sku wh)
        short (max 0 (- q avail))
        reserved (min q avail)]
    {:stock (reserve st sku wh reserved)
     :backordered short}))

;; ---------------------------------------------------------------------------
;; in-transit transfer (2-phase: initiate → receive)
;; ---------------------------------------------------------------------------

(defrecord InTransit [id sku wh-from wh-to qty status])

(defn initiate-transfer
  "Start a 2-phase transfer: decrement source stock (atomic), return an
  InTransit record (status :in-transit) to be received later. Returns
  {:stock s :in-transit InTransit} or {:stock s :error :insufficient} if source
  can't cover the qty."
  [st sku wh-from wh-to qty id]
  (let [q (max 0 qty)]
    (if (available? st sku wh-from q)
      {:stock (reserve st sku wh-from q)
       :in-transit (->InTransit id sku wh-from wh-to q :in-transit)}
      {:stock st :error :insufficient})))

(defn receive-transfer
  "Complete a 2-phase transfer: increment the destination stock. Returns the
  new Stock. The InTransit is consumed (caller records it as :received)."
  [st in-transit]
  (restock st (:sku in-transit) (:wh-to in-transit) (:qty in-transit)))

(defn receive-transfer-activity
  "Build a ledger activity for receiving an in-transit transfer (kind :stock-receive)."
  [in-transit opts]
  (ledger/activity
   (merge {:lane :warehouse :kind :stock-receive
           :title (str "Receive transfer " (:id in-transit))
           :props {:transfer-id (:id in-transit)
                   :sku (:sku in-transit)
                   :qty (:qty in-transit)
                   :warehouse (:wh-to in-transit)}} opts)))

(defn warehouse-activity
  "Project a warehouse event onto chobo.ledger as a :warehouse activity."
  [opts]
  (ledger/activity
   (merge {:lane :warehouse :kind :stock-move} opts)))

;; ---------------------------------------------------------------------------
;; reorder points + low-stock alerts
;; ---------------------------------------------------------------------------

(defrecord ReorderPolicy [sku warehouse reorder-point reorder-qty])

(defn reorder-policy [m] (merge {:reorder-point 0 :reorder-qty 0} m))

(defn below-reorder-point?
  "True if on-hand for sku@wh is at or below the policy's reorder-point."
  [st policy]
  (<= (on-hand st (:sku policy) (:warehouse policy))
      (:reorder-point policy 0)))

(defn low-stock-skus
  "Scan all policies, return those whose stock is at/below their reorder point.
  Returns [{:sku :warehouse :on-hand :reorder-point :reorder-qty}]."
  [st policies]
  (->> policies
       (filterv #(below-reorder-point? st %))
       (mapv (fn [p]
               (assoc p :on-hand (on-hand st (:sku p) (:warehouse p)))))))

(defn auto-reorder
  "For all policies below reorder point, generate restock suggestions. Returns
  [{:sku :warehouse :qty :reorder-point}]. Does NOT mutate stock — the host app
  decides whether to execute the reorder (e.g. create a PO)."
  [st policies]
  (->> policies
       (filterv #(below-reorder-point? st %))
       (mapv (fn [p]
               {:sku (:sku p)
                :warehouse (:warehouse p)
                :qty (:reorder-qty p 0)
                :reorder-point (:reorder-point p 0)
                :current-on-hand (on-hand st (:sku p) (:warehouse p))}))))

(defn reorder-activity
  "Build a ledger activity for a reorder trigger (kind :reorder)."
  [suggestion opts]
  (ledger/activity
   (merge {:lane :warehouse :kind :reorder
           :title (str "Reorder " (:sku suggestion) " for " (:warehouse suggestion))
           :props {:sku (:sku suggestion)
                   :warehouse (:warehouse suggestion)
                   :qty (:qty suggestion 0)
                   :reorder-point (:reorder-point suggestion 0)
                   :current-on-hand (:current-on-hand suggestion 0)}} opts)))
