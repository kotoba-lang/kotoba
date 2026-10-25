(ns madoguchi.ssr
  (:require [shitsuke.hiccup :as hic] [shitsuke.style :as style]
            [madoguchi.views :as views] [madoguchi.ticket :as ticket] [madoguchi.customer :as customer]))

(defn sample-db []
  {:tickets [(-> (ticket/ticket {:id "t1" :customer "u1" :subject "Parka sizing" :priority :normal})
                 (ticket/open) (ticket/add-message {:from :customer :body "Is M true to size?" :timestamp 1}))]
   :customers {"u1" (-> (customer/customer {:id "u1" :name "Alice" :email "a@b"})
                        (customer/add-order-ref "ord_1") (customer/add-lifetime-value 38000)
                        (customer/tag :vip))}})

(defn root-html ([] (root-html (sample-db)))
  ([db] (str "<!doctype html>\n" (hic/->html [:html {:lang "ja"}
                     [:head [:meta {:charset "utf-8"}] [:title "madoguchi SSR"]
                      [:style [:hiccup/raw (style/root-css)]]]
                     [:body (views/root db)]]))))
