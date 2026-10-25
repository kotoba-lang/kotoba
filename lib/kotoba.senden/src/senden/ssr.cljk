(ns senden.ssr
  (:require [shitsuke.hiccup :as hic] [shitsuke.style :as style]
            [senden.views :as views] [senden.campaign :as campaign] [senden.funnel :as funnel]))

(defn sample-db []
  {:campaigns [(-> (campaign/campaign {:id "c1" :name "Spring parka launch" :channel :social})
                   (campaign/schedule) (campaign/start-campaign) (campaign/spend 50000) (campaign/record-conversion 25))]
   :funnel (-> (funnel/funnel) (funnel/set-stage :awareness 1000) (funnel/set-stage :interest 300)
               (funnel/set-stage :consideration 120) (funnel/set-stage :purchase 40) (funnel/set-stage :retention 12))})

(defn root-html ([] (root-html (sample-db)))
  ([db] (str "<!doctype html>\n" (hic/->html [:html {:lang "ja"}
                     [:head [:meta {:charset "utf-8"}] [:title "senden SSR"]
                      [:style [:hiccup/raw (style/root-css)]]]
                     [:body (views/root db)]]))))
