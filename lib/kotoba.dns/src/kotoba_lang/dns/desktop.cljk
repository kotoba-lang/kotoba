(ns kotoba-lang.dns.desktop
  "Entry point for the shadow-cljs :app build
  (appview/etzhayyim-wasm-dns-scndu0rf/web/dist/js/main.js, loaded by
  appview/etzhayyim-wasm-dns-scndu0rf/web/index.html) — same mount pattern
  as murakumo-studio.desktop and cloud-itonami.public-malak.desktop."
  (:require [reagent.dom.client :as rdomc]
            [kotoba-lang.dns.ui :as ui]))

(defonce root (atom nil))

(defn- mount! []
  (let [el (.getElementById js/document "app")]
    (when-not @root
      (reset! root (rdomc/create-root el)))
    (rdomc/render @root [ui/root])))

(defn init! []
  ;; reagent's r/atom re-renders subscribed components on change
  ;; (ui/root derefs state/state) — mount once.
  (mount!))
