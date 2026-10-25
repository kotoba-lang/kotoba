(ns soko.fulfillment
  "Fulfillment planning (pure). Given an order's lines [{:sku :qty}] and a
  Warehouse Stock, allocate to a warehouse (first-fit) and produce a pick-list +
  Shipment. Pure; does not mutate stock (caller reserves via soko.warehouse)."
  (:require [soko.warehouse :as wh]
            [soko.shipment :as ship]))

(defn can-fulfill?
  "True if a single warehouse has all lines in stock. Lines are checked against
  progressively-reserved stock, so two lines for the same sku correctly demand
  their combined qty rather than each being checked against the same starting
  on-hand figure."
  [st wh-id lines]
  (loop [st st lines (seq lines)]
    (or (empty? lines)
        (let [{:keys [sku] :as line} (first lines)
              qty (:qty line 1)]
          (and (wh/available? st sku wh-id qty)
               (recur (wh/reserve st sku wh-id qty) (next lines)))))))

(defn pick-list
  "Produce a pick-list [{:sku :qty :warehouse}] for lines, allocating each line
  to the first warehouse that has it. Returns nil if any line can't be placed.
  Allocations are simulated against progressively-reserved stock, so two lines
  for the same sku correctly compete for the same on-hand quantity instead of
  each being checked against the original, unmodified stock."
  [st lines]
  (loop [st st lines (seq lines) acc []]
    (if (empty? lines)
      (vec acc)
      (let [line (first lines)
            sku (:sku line)
            qty (:qty line 1)
            wh (some (fn [w] (when (wh/available? st sku w qty) w))
                     (wh/warehouses-with-sku st sku))]
        (when wh
          (recur (wh/reserve st sku wh qty) (next lines) (conj acc (assoc line :warehouse wh))))))))

(defn fulfillment-plan
  "Plan fulfillment for an order: pick-list + a draft Shipment per warehouse.
  Returns {:pick-list [...] :shipments [...]} or {:error :cannot-fulfill}."
  [st order-id lines]
  (if-let [pl (pick-list st lines)]
    (let [by-wh (group-by :warehouse pl)]
      {:pick-list pl
       :shipments (for [[wh-id wh-lines] by-wh]
                    (ship/shipment {:id (str "shp_" order-id "_" wh-id)
                                    :order-id order-id
                                    :warehouse wh-id
                                    :lines (map #(select-keys % [:sku :qty]) wh-lines)}))})
    {:error :cannot-fulfill}))

;; ---------------------------------------------------------------------------
;; split shipment (partial fulfillment when no single warehouse covers a line)
;; ---------------------------------------------------------------------------

(defn split-line
  "Split a line {:sku :qty} across warehouses given a Stock. Returns a seq of
  {:sku :qty :warehouse} allocating the qty greedily across warehouses that have
  the sku, until the full qty is covered or stock is exhausted. Records the
  unfulfilled remainder in the last element as {:sku :qty-remaining} when stock
  is insufficient."
  [st line]
  (let [sku (:sku line)
        needed (:qty line 1)
        whs (wh/warehouses-with-sku st sku)]
    (loop [remaining needed
           [w & rest-w] whs
           acc []]
      (cond
        (<= remaining 0) acc
        (nil? w) (if (pos? remaining)
                   (conj acc {:sku sku :qty-remaining remaining})
                   acc)
        :else
        (let [avail (wh/on-hand st sku w)
              take-now (min avail remaining)]
          (if (pos? take-now)
            (recur (- remaining take-now)
                   rest-w
                   (conj acc {:sku sku :qty take-now :warehouse w}))
            (recur remaining rest-w acc)))))))

(defn split-fulfillment-plan
  "Plan split-shipment fulfillment for an order when no single warehouse can
  cover all lines. Splits each line greedily across warehouses. Returns
  {:allocations [...] :shipments [...] :unfulfilled [...]} where allocations
  are the split lines and shipments are grouped by warehouse. Unfulfilled lines
  (insufficient total stock) appear in :unfulfilled. Each line's split is
  simulated against progressively-reserved stock, so two lines for the same
  sku correctly compete for the same on-hand quantity instead of each being
  split against the original, unmodified stock."
  [st order-id lines]
  (let [split-lines (first
                     (reduce (fn [[acc st] line]
                               (let [splits (split-line st line)
                                     st'    (reduce (fn [s {:keys [sku qty warehouse]}]
                                                      (cond-> s warehouse (wh/reserve sku warehouse qty)))
                                                    st splits)]
                                 [(into acc splits) st']))
                             [[] st]
                             lines))
        allocations (filterv :warehouse split-lines)
        unfulfilled (filterv :qty-remaining split-lines)
        by-wh (group-by :warehouse allocations)
        shipments (for [[wh-id wh-lines] by-wh]
                    (ship/shipment {:id (str "shp_" order-id "_" wh-id)
                                    :order-id order-id
                                    :warehouse wh-id
                                    :lines (map #(select-keys % [:sku :qty]) wh-lines)}))]
    {:allocations allocations
     :shipments shipments
     :unfulfilled unfulfilled}))
