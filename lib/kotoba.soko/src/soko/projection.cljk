(ns soko.projection
  "Cross-domain projection: mise.order → soko.fulfillment.

  Bridges retail EC (mise) and warehouse/logistics (soko): a placed mise order's
  items are projected onto a soko fulfillment plan (pick-list + per-warehouse
  shipments), allocated against a multi-location Stock. v1 is a pure stub —
  the host app drives the actual pick/pack/ship state machine and stock
  reservation; this namespace only plans (pure)."
  (:require [mise.order :as order]
            [soko.warehouse :as wh]
            [soko.fulfillment :as ful]
            [soko.shipment :as ship]
            [chobo.ledger :as ledger]))

(defn order-lines
  "Normalize a mise Order's :items into fulfillment lines [{:sku :qty}]. Items
  may carry :slides/qty-style keys or plain :qty; sku comes from :sku or
  :product-id. Tolerates plain maps (no mise dep needed to call)."
  [ord]
  (for [item (:items ord)]
    {:sku (or (:sku item) (:product-id item) (:id item))
     :qty (or (:qty item) 1)}))

(defn order->fulfillment-plan
  "Plan fulfillment for a mise order against a soko multi-location Stock.
  Returns the soko.fulfillment/fulfillment-plan result ({:pick-list :shipments}
  or {:error}). Pure."
  [ord stock]
  (ful/fulfillment-plan stock (:id ord) (order-lines ord)))

(defn can-fulfill-order?
  "True if the stock can fulfill all the order's lines (across warehouses)."
  [ord stock]
  (some? (ful/pick-list stock (order-lines ord))))

(defn fulfillment-activity
  "Project the order→fulfillment event onto chobo.ledger as a :warehouse
  activity (kind :fulfillment-plan). Caller appends to its ILedgerStore."
  [ord plan opts]
  (ledger/activity
   (merge {:lane :warehouse :kind :fulfillment-plan
           :title (str "Fulfillment for order " (:id ord))
           :props {:order-id (:id ord)
                   :shipments (count (:shipments plan))
                   :pick-list-size (count (:pick-list plan))}}
          opts)))
