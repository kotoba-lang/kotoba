(ns kotoba.dtn.ui
  "Operator-facing console for a DTN store-and-forward node.

  Renders an HTML read-only panel of bundles currently in store and link
  reachability, using kotoba-lang/html + css. Pure data → markup: no
  network. This view only observes the store/link state a caller hands
  it — it never renders a write surface (no <form>/<button>)."
  (:require [html.core :as html]
            [css.core :as css]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- bundle-rows [bundles]
  (for [b bundles]
    [:tr [:td (:dtn/bundle-id b)]
     [:td (or (:dtn/source b) "—")]
     [:td (or (:dtn/destination b) "—")]
     [:td.amt (:dtn/lifetime-ms b)]]))

(defn- link-rows [links]
  (for [l links]
    [:tr [:td (:dtn/link-id l)]
     [:td (or (:dtn/neighbor l) "—")]
     [:td (name (:dtn/transport-kind l))]
     [:td (if (:dtn/reachable? l) [:span.ok "✓"] [:span.err "✕"])]
     [:td.amt (or (:dtn/bandwidth-bps l) "—")]]))

(defn dashboard
  "Render a full HTML console for a DTN node operator."
  [{:keys [bundles links]}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "kotoba-dtn · store-and-forward"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "DTN Store-and-Forward — Operator Console"] [:span.badge "read-only"]]
      [:main
       (when (seq bundles)
         [:section.card [:h2 "Bundles in store"]
          [:table [:thead [:tr [:th "Bundle ID"] [:th "Source"] [:th "Destination"] [:th.amt "Lifetime (ms)"]]]
           [:tbody (bundle-rows bundles)]]])
       (when (seq links)
         [:section.card [:h2 "Link reachability"]
          [:table [:thead [:tr [:th "Link ID"] [:th "Neighbor"] [:th "Transport"] [:th ""] [:th.amt "Bandwidth (bps)"]]]
           [:tbody (link-rows links)]]])]]]))
