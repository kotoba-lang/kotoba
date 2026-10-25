(ns senden.views
  "Pure-hiccup marketing components on shitsuke."
  (:require [shitsuke.style :as s]
            [senden.campaign :as campaign]
            [senden.funnel :as funnel]))

(defn class-name [x] (s/class-name x))

(defn campaign-card [c]
  [:article {:class (class-name :campaign-card) :data-campaign (:id c)}
   [:h3 (:name c)]
   [:p "channel: " (name (:channel c :unknown))]
   [:p "status: " (name (:status c :draft))]
   [:p "spend: " (get-in c [:metrics :spend] 0) " / conversions: " (get-in c [:metrics :conversions] 0)]
   (when-let [cpa (campaign/cpa c)] [:p "CPA: " (str cpa)])])

(defn funnel-bar [f]
  [:section {:class (class-name :funnel)}
   (for [stage funnel/stages]
     [:div {:class (class-name :funnel-stage)}
      [:span (name stage)] [:span (funnel/stage-count f stage)]])])

(defn root [db]
  [:div {:class (class-name :senden)}
   [:h1 "Marketing"]
   (into [:section] (map campaign-card (:campaigns db [])))
   (funnel-bar (:funnel db))])
