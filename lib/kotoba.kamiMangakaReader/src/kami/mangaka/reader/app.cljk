(ns kami.mangaka.reader.app
  "Browser reader: reagent + re-frame over the SAME cljc views as the static SSR
  (ADR-2606282101). Progressive enhancement — the page is fully readable as
  server-rendered HTML; mounting this hydrates a live locale switch that
  re-renders only the text overlays (the panel images never reload).

  The static page injects its data + initial locale as EDN on
  `window.__manga` / `window.__locale`; we read it, hold locale in the re-frame
  db, and re-render `views/chapter-view` (or index-view) on change."
  (:require [reagent.dom :as rdom]
            [re-frame.core :as rf]
            [cljs.reader :as edn]
            [kami.mangaka.reader.views :as v]))

;; --- db / events / subs ----------------------------------------------------

(rf/reg-event-db :init
  (fn [_ [_ {:keys [data view locale]}]]
    {:data data :view view :locale locale}))

(rf/reg-event-db :set-locale
  (fn [db [_ loc]] (assoc db :locale loc)))

(rf/reg-sub :locale (fn [db _] (:locale db)))
(rf/reg-sub :data   (fn [db _] (:data db)))
(rf/reg-sub :view   (fn [db _] (:view db)))

;; --- root component --------------------------------------------------------

(defn root []
  (let [view   @(rf/subscribe [:view])
        data   @(rf/subscribe [:data])
        locale @(rf/subscribe [:locale])
        data   (assoc data :locale locale)]
    (case view
      :chapter (v/chapter-view data)
      :index   (v/index-view data)
      [:div "…"])))

;; --- intercept locale-switch clicks (delegate; works on SSR'd or live DOM) --

(defn- wire-lang-switch! []
  (.addEventListener
   js/document "click"
   (fn [e]
     (when-let [a (.closest (.-target e) "a[data-lang]")]
       (.preventDefault e)
       (rf/dispatch [:set-locale (keyword (.getAttribute a "data-lang"))])))))

(defn- read-global [k fallback]
  (if-let [s (aget js/window k)] (edn/read-string s) fallback))

(defn ^:export mount []
  (let [el (.getElementById js/document "mk-app")]
    (when el
      (rf/dispatch-sync [:init {:data   (read-global "__manga" {})
                                :view   (keyword (read-global "__view" "chapter"))
                                :locale (keyword (read-global "__locale" "ja"))}])
      (wire-lang-switch!)
      (rdom/render [root] el))))

(defn ^:export init [] (mount))
