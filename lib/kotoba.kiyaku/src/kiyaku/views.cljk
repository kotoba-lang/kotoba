(ns kiyaku.views
  "Pure-hiccup customer-account + returns components on shitsuke."
  (:require [shitsuke.style :as s]
            [kiyaku.account :as account]
            [kiyaku.returns :as returns]))

(defn class-name [x] (s/class-name x))

(defn account-card [acc]
  [:article {:class (class-name :account-card) :data-account (:id acc)}
   [:h3 (:name acc)]
   [:p (:email acc)]
   [:p "wallet: " (:wallet-balance acc 0)]
   (when-let [addr (account/default-address acc)]
     [:p "default ship: " (:line1 addr) " " (:city addr)])])

(defn return-row [r]
  [:div {:class (class-name :return-row) :data-return (:id r)}
   [:span {:class (class-name :return-status)} (name (:status r :requested))]
   [:span "RMA " (:id r) " / order " (:order-id r)]
   [:span "items: " (returns/total-return-qty r)]])

(defn root [db]
  [:div {:class (class-name :kiyaku)}
   [:h1 "Customer accounts and returns"]
   (into [:section] (map account-card (vals (:accounts db {}))))
   (into [:section] (map return-row (:returns db [])))])
