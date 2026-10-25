(ns murakumo-studio.desktop
  "Entry point for the shadow-cljs :app build (desktop/dist/js/main.js, loaded
  by desktop/dist/index.html). Polls the local engine sidecar until it's ready
  (the Rust shell spawns it on startup; JVM boot + inference lib load takes a
  few seconds), then loads the model list."
  (:require [reagent.dom.client :as rdomc]
            [murakumo-studio.state :as state]
            [murakumo-studio.client :as client]
            [murakumo-studio.ui :as ui]))

(defonce root (atom nil))

(defn- mount! []
  (let [el (.getElementById js/document "app")]
    (when-not @root
      (reset! root (rdomc/create-root el)))
    (rdomc/render @root [ui/root])))

(defn- poll-engine! []
  (-> (client/health)
      (.then (fn [_]
               (swap! state/state assoc :engine {:status :ready :error nil})
               (-> (client/scan-local-models) (.catch (constantly nil)))
               (-> (client/list-models)
                   (.then (fn [res]
                            (swap! state/state update :models merge {:items (:data res)})))
                   (.catch (constantly nil)))))
      (.catch (fn [_]
                (swap! state/state assoc :engine {:status :starting :error nil})
                (js/setTimeout poll-engine! 1000)))))

(defn init! []
  ;; reagent's r/atom already re-renders subscribed components on change
  ;; (murakumo-studio.ui/root derefs state/state) — mount once.
  (mount!)
  (poll-engine!))
