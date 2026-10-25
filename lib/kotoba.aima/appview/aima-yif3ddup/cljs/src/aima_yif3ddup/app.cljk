(ns aima-yif3ddup.app
  "aima-yif3ddup — reagent + re-frame scaffold, migrated from the Svelte
  Vite entry scaffold that used to live at
  appview/aima-yif3ddup/svelte/src/App.svelte (\"Vite entry scaffold
  after SvelteKit cleanup.\").

  This is still a scaffold — the original had no business logic to port —
  but it wires a real event -> db -> sub -> view round-trip through
  re-frame instead of being static markup, and renders through
  jp-go-dds.core (デジタル庁デザインシステム) instead of hand-rolled CSS."
  (:require [reagent.dom :as rdom]
            [re-frame.core :as rf]
            [jp-go-dds.core :as dds]))

;; --- db ----------------------------------------------------------------------

(def default-db
  {:app-name "aima-yif3ddup"
   :tagline "ClojureScript scaffold (reagent + re-frame) — migrated from the Svelte/Vite entry scaffold."
   :clicks 0})

(rf/reg-event-db
 ::initialize-db
 (fn [_ _] default-db))

(rf/reg-event-db
 ::increment-clicks
 (fn [db _] (update db :clicks inc)))

(rf/reg-sub
 ::app-name
 (fn [db _] (:app-name db)))

(rf/reg-sub
 ::tagline
 (fn [db _] (:tagline db)))

(rf/reg-sub
 ::clicks
 (fn [db _] (:clicks db)))

;; --- view ----------------------------------------------------------------------

(defn app-view []
  (let [app-name @(rf/subscribe [::app-name])
        tagline  @(rf/subscribe [::tagline])
        clicks   @(rf/subscribe [::clicks])]
    (dds/container
     [:div {:class "dds-ext-center"}
      (dds/heading 1 app-name)
      [:p {:class "dds-ext-lead"} tagline]
      (dds/card
       [:p (str "clicks: " clicks)]
       (dds/button "Click" {:type :outline
                             :attrs {:on-click #(rf/dispatch [::increment-clicks])}}))])))

(defn ^:export main []
  (rf/dispatch-sync [::initialize-db])
  (rdom/render [app-view] (.getElementById js/document "app")))
