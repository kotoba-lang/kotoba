(ns soko.ssr
  (:require [shitsuke.hiccup :as hic] [shitsuke.style :as style]
            [soko.views :as views] [soko.warehouse :as wh] [soko.shipment :as ship]))

(defn sample-db []
  (let [st (-> (wh/stock-from [["ph-m" "wh-tokyo" 10] ["ph-l" "wh-tokyo" 5] ["ph-m" "wh-osaka" 3]])
               (wh/transfer "ph-m" "wh-tokyo" "wh-osaka" 2))]
    {:stock st
     :shipments [(-> (ship/shipment {:id "shp_1" :order-id "ord_1" :warehouse "wh-tokyo" :carrier "yamato"
                                     :lines [{:sku "ph-m" :qty 1}]})
                     (ship/pick) (ship/pack) (ship/ship) (ship/set-tracking "1234"))]}))

(defn root-html ([] (root-html (sample-db)))
  ([db] (str "<!doctype html>\n" (hic/->html [:html {:lang "ja"}
                     [:head [:meta {:charset "utf-8"}] [:title "soko SSR"]
                      [:style [:hiccup/raw (style/root-css)]]]
                     [:body (views/root db)]]))))
