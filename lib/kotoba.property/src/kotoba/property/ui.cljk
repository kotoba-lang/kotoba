(ns kotoba.property.ui
  "Operator-facing console for a community real-estate-agency actor.

  Renders an HTML read-only panel of parcels, listings and leases (with
  term-overlap warnings), using kotoba-lang/html + css. Pure data → markup:
  no network. The governor gates listing/lease/disclosure; this view only
  observes."
  (:require [html.core :as html]
            [css.core :as css]
            [kotoba.property :as prop]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- money [n currency] (str (or n 0) " " (or currency "USD")))

(defn- parcel-rows [parcels]
  (for [p parcels]
    [:tr [:td (:parcel/id p)]
     [:td (or (:parcel/address p) "—")]
     [:td.amt (or (:parcel/area-m2 p) "—")]
     [:td (name (or (:parcel/zoning p) :unspecified))]]))

(defn- listing-rows [listings]
  (for [l listings]
    [:tr [:td (:listing/id l)]
     [:td (:listing/parcel l)]
     [:td (name (:listing/type l))]
     [:td.amt (money (:listing/price l) (:listing/currency l))]
     [:td (or (:listing/agent l) "—")]]))

(defn- overlap-badge [lease others]
  (if (some #(prop/term-overlaps? lease %) others)
    [:span.warn "overlap"]
    [:span.ok "clear"]))

(defn- lease-rows [leases]
  (for [l leases]
    [:tr [:td (:lease/id l)]
     [:td (:lease/parcel l)]
     [:td (or (:lease/tenant l) "—")]
     [:td (or (:lease/landlord l) "—")]
     [:td.amt (money (:lease/rent l) (:lease/currency l))]
     [:td (str (:lease/start l) " → " (:lease/end l))]
     [:td (overlap-badge l (remove #{l} leases))]]))

(defn dashboard
  "Render a full HTML console for a real-estate-agency operator."
  [{:keys [parcels listings leases] :as ctx}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · real-estate"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "Real-Estate Agency — Operator Console"] [:span.badge "read-only · governor-gated"]]
      [:main
       (when (seq parcels)
         [:section.card [:h2 "Parcels"]
          [:table [:thead [:tr [:th "ID"] [:th "Address"] [:th.amt "Area (m²)"] [:th "Zoning"]]]
           [:tbody (parcel-rows parcels)]]])
       (when (seq listings)
         [:section.card [:h2 "Listings"]
          [:table [:thead [:tr [:th "ID"] [:th "Parcel"] [:th "Type"] [:th.amt "Price"] [:th "Agent"]]]
           [:tbody (listing-rows listings)]]])
       (when (seq leases)
         [:section.card [:h2 "Leases (term-overlap checked)"]
          [:table [:thead [:tr [:th "ID"] [:th "Parcel"] [:th "Tenant"] [:th "Landlord"] [:th.amt "Rent"] [:th "Term"] [:th "Overlap"]]]
           [:tbody (lease-rows leases)]]])]]]))
