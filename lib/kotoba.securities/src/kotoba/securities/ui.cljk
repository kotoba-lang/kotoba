(ns kotoba.securities.ui
  "Operator-facing console for a securities/fund actor (holding companies,
  trusts/funds, market administration, brokerage, fund management).

  Renders an HTML read-only panel of positions, trades and fund NAVs,
  using kotoba-lang/html + css. Pure data -> markup: no network. The
  governor gates trade execution/distribution/NAV publication; this view
  only observes."
  (:require [html.core :as html]
            [css.core :as css]))

(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- money [n currency] (str (or n 0) " " (or currency "USD")))

(defn- position-rows [positions]
  (for [p positions]
    [:tr [:td (:position/id p)]
     [:td (or (:position/holder p) "—")]
     [:td (or (:position/instrument p) "—")]
     [:td.amt (:position/quantity p)]]))

(defn- trade-rows [trades]
  (for [t trades]
    [:tr [:td (:trade/id t)]
     [:td (:trade/account t)]
     [:td (name (or (:trade/side t) :unspecified))]
     [:td.amt (:trade/quantity t)]
     [:td.amt (money (:trade/price t) (:trade/currency t))]]))

(defn- nav-rows [navs]
  (for [n navs]
    [:tr [:td (:nav/fund n)]
     [:td.amt (money (:nav/net-assets n) (:nav/currency n))]
     [:td.amt (:nav/outstanding-units n)]
     [:td.amt (money (:nav/per-share n) (:nav/currency n))]]))

(defn dashboard
  "Render a full HTML console for a securities/fund operator."
  [{:keys [positions trades navs]}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · securities"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "Securities/Fund — Operator Console"] [:span.badge "read-only · governor-gated"]]
      [:main
       (when (seq positions)
         [:section.card [:h2 "Positions"]
          [:table [:thead [:tr [:th "ID"] [:th "Holder"] [:th "Instrument"] [:th.amt "Qty"]]]
           [:tbody (position-rows positions)]]])
       (when (seq trades)
         [:section.card [:h2 "Trades"]
          [:table [:thead [:tr [:th "ID"] [:th "Account"] [:th "Side"] [:th.amt "Qty"] [:th.amt "Price"]]]
           [:tbody (trade-rows trades)]]])
       (when (seq navs)
         [:section.card [:h2 "Fund NAV"]
          [:table [:thead [:tr [:th "Fund"] [:th.amt "Net Assets"] [:th.amt "Units"] [:th.amt "NAV/Share"]]]
           [:tbody (nav-rows navs)]]])]]]))
