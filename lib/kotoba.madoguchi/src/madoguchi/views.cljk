(ns madoguchi.views
  "Pure-hiccup support/CRM components on shitsuke."
  (:require [shitsuke.style :as s]
            [madoguchi.ticket :as ticket]
            [madoguchi.customer :as customer]))

(defn class-name [x] (s/class-name x))

(defn ticket-row [t]
  [:div {:class (class-name :ticket-row) :data-ticket (:id t)}
   [:span {:class (class-name :ticket-status)} (name (:status t :new))]
   [:span {:class (class-name :ticket-priority)} (name (:priority t :normal))]
   [:span (:subject t)]
   [:span (:customer t)]])

(defn customer-card [c]
  [:article {:class (class-name :customer-card) :data-customer (:id c)}
   [:h3 (:name c)]
   [:p (:email c)]
   [:p "LTV: " (:lifetime-value c 0) " / orders: " (count (:order-refs c []))]
   [:p "tags: " (str (:tags c #{}))]])

(defn root [db]
  [:div {:class (class-name :madoguchi)}
   [:h1 "Customer support"]
   (into [:section] (map ticket-row (:tickets db [])))
   (into [:section] (map customer-card (vals (:customers db {}))))])
