(ns kiyaku.events
  "re-frame events + subs for kiyaku (portable 7-fn subset)."
  (:require #?(:cljs [re-frame.core :as rf] :clj [shitsuke.re-frame.core :as rf])
            [kiyaku.account :as account]
            [kiyaku.returns :as returns]))

(defn register! []
  (rf/reg-event-db :kiyaku/init (fn [_ _] {:accounts {} :returns []}))
  (rf/reg-event-db :account/loaded (fn [db [_ acc]] (assoc-in db [:accounts (:id acc)] acc)))
  (rf/reg-event-db :account/add-address
    (fn [db [_ id addr]] (update-in db [:accounts id] #(account/add-address % addr))))
  (rf/reg-event-db :return/add (fn [db [_ r]] (update db :returns conj r)))
  (rf/reg-event-db :return/transition
    (fn [db [_ id to]] (update db :returns (fn [xs] (mapv #(if (= (:id %) id) (or (returns/transition % to) %) %) xs)))))
  (rf/reg-sub :kiyaku/accounts (fn [db _] (:accounts db {})))
  (rf/reg-sub :kiyaku/account (fn [db _] (fn [id] (get-in db [:accounts id]))))
  (rf/reg-sub :kiyaku/returns (fn [db _] (:returns db [])))
  (rf/reg-sub :kiyaku/open-returns (fn [db _] (filterv #(#{:requested :approved :shipped :received} (:status % :requested)) (:returns db []))))
  nil)
