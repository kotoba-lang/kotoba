(ns senden.events
  "re-frame events + subs for senden (portable 7-fn subset via shitsuke)."
  (:require #?(:cljs [re-frame.core :as rf] :clj [shitsuke.re-frame.core :as rf])
            [senden.campaign :as campaign]
            [senden.funnel :as funnel]))

(defn register! []
  (rf/reg-event-db :senden/init (fn [_ _] {:campaigns [] :funnel (funnel/funnel)}))
  (rf/reg-event-db :campaign/add (fn [db [_ c]] (update db :campaigns conj c)))
  (rf/reg-event-db :campaign/transition
    (fn [db [_ id to]] (update db :campaigns (fn [xs] (mapv #(if (= (:id %) id) (or (campaign/transition % to) %) %) xs)))))
  (rf/reg-event-db :campaign/spend
    (fn [db [_ id amt]] (update db :campaigns (fn [xs] (mapv #(if (= (:id %) id) (campaign/spend % amt) %) xs)))))
  (rf/reg-event-db :campaign/convert
    (fn [db [_ id n]] (update db :campaigns (fn [xs] (mapv #(if (= (:id %) id) (campaign/record-conversion % n) %) xs)))))
  (rf/reg-event-db :funnel/set (fn [db [_ stage n]] (update db :funnel #(funnel/set-stage % stage n))))
  (rf/reg-sub :senden/campaigns (fn [db _] (:campaigns db [])))
  (rf/reg-sub :senden/funnel (fn [db _] (:funnel db)))
  (rf/reg-sub :senden/campaign-by-id (fn [db _] (fn [id] (some #(when (= (:id %) id) %) (:campaigns db [])))))
  nil)
