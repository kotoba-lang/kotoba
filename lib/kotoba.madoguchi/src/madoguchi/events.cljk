(ns madoguchi.events
  "re-frame events + subs for madoguchi (portable 7-fn subset)."
  (:require #?(:cljs [re-frame.core :as rf] :clj [shitsuke.re-frame.core :as rf])
            [madoguchi.ticket :as ticket]
            [madoguchi.customer :as customer]))

(defn register! []
  (rf/reg-event-db :madoguchi/init (fn [_ _] {:tickets [] :customers {}}))
  (rf/reg-event-db :ticket/add (fn [db [_ t]] (update db :tickets conj t)))
  (rf/reg-event-db :ticket/transition
    (fn [db [_ id to]] (update db :tickets (fn [xs] (mapv #(if (= (:id %) id) (or (ticket/transition % to) %) %) xs)))))
  (rf/reg-event-db :ticket/message
    (fn [db [_ id msg]] (update db :tickets (fn [xs] (mapv #(if (= (:id %) id) (ticket/add-message % msg) %) xs)))))
  (rf/reg-event-db :customer/loaded (fn [db [_ c]] (assoc-in db [:customers (:id c)] c)))
  (rf/reg-event-db :customer/tag (fn [db [_ id t]] (update-in db [:customers id] #(customer/tag % t))))
  (rf/reg-sub :madoguchi/tickets (fn [db _] (:tickets db [])))
  (rf/reg-sub :madoguchi/open-tickets (fn [db _] (filterv #(#{:new :open :pending} (:status % :new)) (:tickets db []))))
  (rf/reg-sub :madoguchi/customers (fn [db _] (:customers db {})))
  (rf/reg-sub :madoguchi/customer (fn [db _] (fn [id] (get-in db [:customers id]))))
  nil)
