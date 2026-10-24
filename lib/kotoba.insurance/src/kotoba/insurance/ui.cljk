(ns kotoba.insurance.ui
  "Operator-facing console for an insurance actor (underwriting/claims/brokerage).

  Renders an HTML read-only panel of policies, premium quotes and claims,
  using kotoba-lang/html + css. Pure data -> markup: no network. The
  governor gates binding/payout/disclosure; this view only observes."
  (:require [html.core :as html]
            [css.core :as css]))

(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- money [n currency] (str (or n 0) " " (or currency "USD")))

(defn- policy-rows [policies]
  (for [p policies]
    [:tr [:td (:policy/id p)]
     [:td (or (:policy/holder p) "—")]
     [:td (name (or (:policy/type p) :unspecified))]
     [:td.amt (money (:policy/coverage p) (:policy/currency p))]
     [:td (str (:policy/start p) " → " (:policy/end p))]]))

(defn- premium-rows [premiums]
  (for [q premiums]
    [:tr [:td (:premium/policy q)]
     [:td.amt (:premium/rate q)]
     [:td.amt (money (:premium/amount q) (:premium/currency q))]]))

(defn- claim-badge [status]
  (if (contains? #{:approved :paid} status)
    [:span.ok (name status)]
    (if (= status :denied) [:span.warn (name status)] [:span.badge (name status)])))

(defn- claim-rows [claims]
  (for [c claims]
    [:tr [:td (:claim/id c)]
     [:td (:claim/policy c)]
     [:td (or (:claim/claimant c) "—")]
     [:td.amt (money (:claim/amount-requested c) (:claim/currency c))]
     [:td (claim-badge (:claim/status c))]]))

(defn dashboard
  "Render a full HTML console for an insurance operator."
  [{:keys [policies premiums claims]}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · insurance"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "Insurance — Operator Console"] [:span.badge "read-only · governor-gated"]]
      [:main
       (when (seq policies)
         [:section.card [:h2 "Policies"]
          [:table [:thead [:tr [:th "ID"] [:th "Holder"] [:th "Type"] [:th.amt "Coverage"] [:th "Term"]]]
           [:tbody (policy-rows policies)]]])
       (when (seq premiums)
         [:section.card [:h2 "Premium quotes"]
          [:table [:thead [:tr [:th "Policy"] [:th.amt "Rate ‰"] [:th.amt "Premium"]]]
           [:tbody (premium-rows premiums)]]])
       (when (seq claims)
         [:section.card [:h2 "Claims"]
          [:table [:thead [:tr [:th "ID"] [:th "Policy"] [:th "Claimant"] [:th.amt "Requested"] [:th "Status"]]]
           [:tbody (claim-rows claims)]]])]]]))
