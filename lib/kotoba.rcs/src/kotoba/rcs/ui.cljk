(ns kotoba.rcs.ui
  "Operator-facing console for an RCS-capable telecommunications-access
  actor.

  Renders an HTML read-only panel of capability-checked E.164 endpoints,
  recent chat messages and receipts, using kotoba-lang/html + css. Pure
  data → markup: no network. The governor gates provisioning/sending; this
  view only observes."
  (:require [kotoba.lang.text :as str]
            [html.core :as html]
            [css.core :as css]
            [kotoba.rcs :as rcs]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- capability-rows [caps]
  (for [c caps]
    (let [ok (rcs/valid-capabilities? c)]
      [:tr [:td (if ok [:span.ok "✓"] [:span.err "✕"])]
           [:td (str (:rcs/endpoint c))]
           [:td (if ok
                  (str/join ", " (map name (sort (:rcs/features c))))
                  "—")]])))

(defn- chat-message-rows [messages]
  (for [m messages]
    [:tr [:td (:rcs/message-id m)]
     [:td (or (:rcs/from m) "—")]
     [:td (or (:rcs/to m) "—")]
     [:td (str (:rcs/body m))]]))

(defn- receipt-rows [receipts]
  (for [r receipts]
    [:tr [:td (:rcs/message-id r)]
     [:td (if (:rcs/disposition r) (name (:rcs/disposition r)) "—")]
     [:td (or (:rcs/timestamp r) "—")]]))

(defn dashboard
  "Render a full HTML console for an RCS operator."
  [{:keys [capabilities messages receipts]}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · rcs"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "RCS — Operator Console"] [:span.badge "read-only · governor-gated"]]
      [:main
       (when (seq capabilities)
         [:section.card [:h2 "Capability discovery"]
          [:table [:thead [:tr [:th ""] [:th "Endpoint"] [:th "Features"]]]
           [:tbody (capability-rows capabilities)]]])
       (when (seq messages)
         [:section.card [:h2 "Recent chat messages"]
          [:table [:thead [:tr [:th "ID"] [:th "From"] [:th "To"] [:th "Body"]]]
           [:tbody (chat-message-rows messages)]]])
       (when (seq receipts)
         [:section.card [:h2 "Delivery / read receipts"]
          [:table [:thead [:tr [:th "Message ID"] [:th "Disposition"] [:th "Timestamp"]]]
           [:tbody (receipt-rows receipts)]]])]]]))
