(ns kotoba.omise.ui
  "Operator-facing console for a community last-mile courier actor.

  Renders an HTML read-only panel of stores (with an open/closed badge for
  a caller-supplied moment) and pickup points, using kotoba-lang/html +
  css. Pure data → markup: no network, no clock. The governor gates
  dispatch/settlement; this view only observes."
  (:require [html.core :as html]
            [css.core :as css]
            [kotoba.omise :as omise]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- open-badge [s [day hhmm]]
  (cond
    (not (omise/active? s))          [:span.err (name (:omise/status s))]
    (omise/open-at? s day hhmm)      [:span.ok "open"]
    :else                            [:span.muted "closed"]))

(defn- store-rows [stores at]
  (for [s stores]
    [:tr [:td (:omise/id s)]
     [:td (:omise/name s)]
     [:td (:omise/address s)]
     [:td (or (:omise/jurisdiction s) "—")]
     [:td (if (:omise/pickup-ready? s) [:span.ok "✓"] [:span.muted "—"])]
     [:td (open-badge s at)]]))

(defn- pickup-rows [points]
  (for [p points]
    [:tr [:td (:pickup/id p)]
     [:td (:pickup/store p)]
     [:td (or (:pickup/label p) "—")]
     [:td (if-let [g (:pickup/geo p)] (str (:lat g) "," (:lng g)) "—")]]))

(defn dashboard
  "Render a full HTML console for a courier operator's store directory.
  ctx: {:stores [..] :pickup-points [..] :at [:mon \"10:00\"]}."
  [{:keys [stores pickup-points at]}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · omise"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "Stores — Operator Console"] [:span.badge "read-only · governor-gated"]]
      [:main
       (when (seq stores)
         [:section.card [:h2 "Stores"]
          [:table [:thead [:tr [:th "ID"] [:th "Name"] [:th "Address"] [:th "Jurisdiction"] [:th "Pickup"] [:th (str "At " (some-> at first name) " " (second at))]]]
           [:tbody (store-rows stores at)]]])
       (when (seq pickup-points)
         [:section.card [:h2 "Pickup points"]
          [:table [:thead [:tr [:th "ID"] [:th "Store"] [:th "Label"] [:th "Geo"]]]
           [:tbody (pickup-rows pickup-points)]]])]]]))
