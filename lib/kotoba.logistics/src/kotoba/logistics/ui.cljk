(ns kotoba.logistics.ui
  "Operator-facing console for a community freight-transport actor.

  Renders an HTML read-only panel of tracking validation, shipments and
  consignments, using kotoba-lang/html + css. Pure data → markup: no
  network. The governor gates dispatch/settlement; this view only observes."
  (:require [html.core :as html]
            [css.core :as css]
            [kotoba.logistics :as log]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- status-badge [s]
  (cond
    (= :delivered (:shipment/status s)) [:span.ok "delivered"]
    (= :in-transit (:shipment/status s)) [:span.warn "in-transit"]
    (= :exception (:shipment/status s)) [:span.err "exception"]
    :else [:span.muted (name (:shipment/status s))]))

(defn- tracking-rows [nums]
  (for [t nums]
    (let [r (log/validate-tracking t)]
      [:tr [:td (if (:logistics/valid? r) [:span.ok "✓"] [:span.err "✕"])]
           [:td (str t)]
           [:td (or (:logistics/normalized r) "—")]])))

(defn- shipment-rows [shipments]
  (for [s shipments]
    [:tr [:td (:shipment/id s)]
     [:td (:shipment/origin s)]
     [:td (:shipment/destination s)]
     [:td (:shipment/carrier s)]
     [:td (or (:shipment/tracking s) "—")]
     [:td (status-badge s)]]))

(defn- consignment-rows [cons]
  (for [c cons]
    [:tr [:td (:cons/id c)]
     [:td (:cons/shipment c)]
     [:td (count (:cons/route c))]
     [:td (or (:cons/declared-value c) "—")]
     [:td (name (:cons/status c))]]))

(defn dashboard
  "Render a full HTML console for a freight-transport operator."
  [{:keys [trackings shipments consignments] :as ctx}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · freight"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "Freight Transport — Operator Console"] [:span.badge "read-only · governor-gated"]]
      [:main
       (when (seq trackings)
         [:section.card [:h2 "Tracking validation"]
          [:table [:thead [:tr [:th ""] [:th "Tracking #"] [:th "Normalized"]]]
           [:tbody (tracking-rows trackings)]]])
       (when (seq shipments)
         [:section.card [:h2 "Shipments"]
          [:table [:thead [:tr [:th "ID"] [:th "Origin"] [:th "Destination"] [:th "Carrier"] [:th "Tracking"] [:th "Status"]]]
           [:tbody (shipment-rows shipments)]]])
       (when (seq consignments)
         [:section.card [:h2 "Consignments"]
          [:table [:thead [:tr [:th "ID"] [:th "Shipment"] [:th "Legs"] [:th "Declared value"] [:th "Status"]]]
           [:tbody (consignment-rows consignments)]]])]]]))
