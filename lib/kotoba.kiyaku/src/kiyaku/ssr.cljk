(ns kiyaku.ssr
  (:require [shitsuke.hiccup :as hic] [shitsuke.style :as style]
            [kiyaku.views :as views] [kiyaku.account :as account] [kiyaku.returns :as returns]))

(defn sample-db []
  {:accounts {"u1" (-> (account/account {:id "u1" :email "a@b" :name "Alice"})
                       (account/add-address {:id "addr1" :label "home" :line1 "1-2-3" :city "Tokyo" :postal "100-0001" :country "JP" :default? true})
                       (account/adjust-wallet 5000))}
   :returns [(-> (returns/return-request {:id "rma_1" :order-id "ord_1" :account-id "u1"
                                          :items [{:sku "ph-m" :qty 1 :reason :wrong-size}]})
                 (returns/approve) (returns/mark-shipped))]})

(defn root-html ([] (root-html (sample-db)))
  ([db] (str "<!doctype html>\n" (hic/->html [:html {:lang "ja"}
                     [:head [:meta {:charset "utf-8"}] [:title "kiyaku SSR"]
                      [:style [:hiccup/raw (style/root-css)]]]
                     [:body (views/root db)]]))))
