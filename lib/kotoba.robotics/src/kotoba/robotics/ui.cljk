(ns kotoba.robotics.ui
  "Operator-facing safety console for a robotics actor.

  Renders an HTML read-only panel of robot missions and the governor's
  action gate decisions, using kotoba-lang/html + css. Pure data → markup:
  no network, no DOM. The governor gates hardware dispatch; this view only
  observes missions, actions and sign-off state — it never dispatches."
  (:require [kotoba.lang.text] [html.core :as html]
            [css.core :as css]
            [kotoba.robotics :as rob]))

;; Domain-specific rules layered on top of the shared operator-theme (css.core).
(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn safety-class [s]
  (cond
    (= s :safety-critical) :critical
    (contains? #{:high} s) :err
    (contains? #{:medium} s) :warn
    :else :ok))

(defn- gate-badge [decision]
  (case (:gate/decision decision)
    :permit          [:span.ok "permit"]
    :deny            [:span.err (str "deny · " (:gate/reason decision "—"))]
    :require-sign-off [:span.warn (str "sign-off · " (name (:gate/safety decision)))]
    [:span.err "invalid"]))

(defn missions-table [missions]
  [:table
   [:thead [:tr [:th "Mission"] [:th "Robot"] [:th "Objective"] [:th "Status"]]]
   [:tbody (for [m missions]
             [:tr [:td (:mission/id m)]
                  [:td (:mission/robot m)]
                  [:td (:mission/objective m)]
                  [:td (name (:mission/status m))]])]])

(defn actions-table [actions allowed]
  [:table
   [:thead [:tr [:th "Action"] [:th "Kind"] [:th "Safety"] [:th "Gate"]]]
   [:tbody
    (for [a actions]
      (let [dec (rob/gate a allowed)]
        [:tr
         [:td (:action/id a)]
         [:td (name (:action/kind a))]
         [:td {:class [(safety-class (:action/safety a))]} (name (:action/safety a))]
         [:td (gate-badge dec)]]))]])

(defn dashboard
  "Render a full HTML safety console page for a robotics operator."
  [{:keys [missions actions allowed-safety] :as ctx
    :or {allowed-safety #{:none :low :medium}}}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "cloud-itonami · robotics"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar
       [:h1 "Robotics Safety — Operator Console"]
       [:span.badge "read-only · governor-gated · never dispatches"]]
      [:main
       [:section.card [:h2 "Missions"] (missions-table missions)]
       (when (seq actions)
         [:section.card [:h2 "Action gate"]
          [:p.muted (str "allowed safety classes: "
                         (kotoba.lang.text/join ", " (map name (sort allowed-safety))))]
          (actions-table actions allowed-safety)])]]]))
