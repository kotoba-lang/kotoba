(ns soko.views
  "Pure-hiccup warehouse/logistics components on shitsuke."
  (:require [shitsuke.style :as s]
            [soko.warehouse :as wh]
            [soko.shipment :as ship]))

(defn class-name [x] (s/class-name x))

(defn stock-row [st sku wh]
  [:div {:class (class-name :stock-row)}
   [:span sku] [:span wh] [:span (wh/on-hand st sku wh)]])

(defn shipment-row [s]
  [:div {:class (class-name :shipment-row) :data-shipment (:id s)}
   [:span {:class (class-name :shipment-status)} (name (:status s :pending))]
   [:span (:id s) " / order " (:order-id s) " / wh " (:warehouse s)]
   (when (:tracking s) [:span " tracking: " (:tracking s)])])

(defn root [db]
  (let [st (:stock db)]
    [:div {:class (class-name :soko)}
     [:h1 "Warehouse / logistics"]
     (into [:section] (for [[sku whs] (:levels st) wh (keys whs)] (stock-row st sku wh)))
     (into [:section] (map shipment-row (:shipments db [])))]))
