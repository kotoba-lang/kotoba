(ns soko.events
  "re-frame events + subs for soko (portable 7-fn subset)."
  (:require #?(:cljs [re-frame.core :as rf] :clj [shitsuke.re-frame.core :as rf])
            [soko.warehouse :as wh]
            [soko.shipment :as ship]))

(defn register! []
  (rf/reg-event-db :soko/init (fn [_ _] {:stock (wh/stock {}) :shipments []}))
  (rf/reg-event-db :stock/restock (fn [db [_ sku wh qty]] (update db :stock #(wh/restock % sku wh qty))))
  (rf/reg-event-db :stock/reserve (fn [db [_ sku wh qty]] (update db :stock #(wh/reserve % sku wh qty))))
  (rf/reg-event-db :stock/transfer (fn [db [_ sku from to qty]] (update db :stock #(wh/transfer % sku from to qty))))
  (rf/reg-event-db :shipment/add (fn [db [_ s]] (update db :shipments conj s)))
  (rf/reg-event-db :shipment/transition
    (fn [db [_ id to]] (update db :shipments (fn [xs] (mapv #(if (= (:id %) id) (or (ship/transition % to) %) %) xs)))))
  (rf/reg-sub :soko/stock (fn [db _] (:stock db)))
  (rf/reg-sub :soko/on-hand (fn [db _] (fn [sku wh] (wh/on-hand (:stock db) sku wh))))
  (rf/reg-sub :soko/shipments (fn [db _] (:shipments db [])))
  nil)
