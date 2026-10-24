(ns kotoba.retail.ui
  "Operator-facing dashboard for a community retail actor.

  Renders an HTML read-only panel from retail records (inventory, receipts,
  reorder queue) using kotoba-lang/html + css. Pure data → markup: no
  network, no DOM. The governor decides sales/voids/reorders; this view only
  observes."
  (:require [html.core :as html]
            [css.core :as css]
            [kotoba.retail :as retail]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- money [n currency] (str (or n 0) " " (or currency "USD")))

(defn- reorder-badge [inv]
  (if (retail/needs-reorder? inv)
    [:span.warn "reorder"]
    [:span.ok "ok"]))

(defn inventory-table [inventories]
  [:table
   [:thead [:tr [:th "SKU"] [:th "Location"] [:th.amt "Qty"] [:th.amt "Reorder at"] [:th "Status"]]]
   [:tbody (for [i inventories]
             [:tr [:td (:inv/sku i)]
                  [:td (:inv/location i)]
                  [:td.amt (:inv/quantity i)]
                  [:td.amt (or (:inv/reorder-at i) "—")]
                  [:td (reorder-badge i)]])]])

(defn receipt-card [r]
  [:section.card
   [:h2 (str "Receipt " (:receipt/id r))]
   [:table
    [:thead [:tr [:th "SKU"] [:th.amt "Price"] [:th.amt "Qty"] [:th.amt "Net"]]]
    [:tbody (for [li (:receipt/items r)]
              [:tr [:td (:li/sku li)]
                   [:td.amt (:li/price li)]
                   [:td.amt (:li/qty li)]
                   [:td.amt (:li/net li)]])]]
   [:p [:strong "Net: "] (money (:receipt/net r) (:receipt/currency r))
    " · Tax: " (money (:receipt/tax r) (:receipt/currency r))
    " · Total: " (money (:receipt/total r) (:receipt/currency r))]])

(defn dashboard
  "Render a full HTML dashboard page for a retail operator."
  [{:keys [inventories receipts] :as ctx}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · retail"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar
       [:h1 "Community Retail — Operator Console"]
       [:span.badge "read-only · governor-gated"]]
      [:main
       [:section.card [:h2 "Inventory"] (inventory-table inventories)]
       (for [r receipts] (receipt-card r))]]]))
