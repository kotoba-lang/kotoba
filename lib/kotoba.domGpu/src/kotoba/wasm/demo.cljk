(ns kotoba.wasm.demo
  "Reference kotoba WASM UI host demo.
   The app uses reagent/re-frame-shaped APIs. The host renders it through
   kotoba:dom ABI onto canvas/WebGL instead of browser DOM widgets."
  (:require [kotoba.wasm.host.webgl :as webgl]
            [kotoba.wasm.debug :as debug]
            [kotoba.wasm.runtime :as runtime]
            [re-frame.core :as rf]))

(defonce runtime-state (atom nil))

(defn app []
  [:main.demo {:style {:padding 18 :width 620 :background "#121724"}}
   [:h1 "kotoba DOM on WebGL"]
   [:p "Reagent/re-frame style UI, rendered without DOM widgets."]
   [:p {:style {:padding 8 :max-width 500}}
    "pointer-events:none proof: the orange overlay below is painted "
    "directly on top of the increment button, fully covering it. "
    "Previously pointer-events:none was never consulted by hit-test, "
    "so a click here would hit nothing -- clicking anywhere in the "
    "overlay's area should still increment the counter, since the "
    "overlay must be fully transparent to pointer events."]
   [:div {:style {:position "relative" :width 120 :height 30}}
    [:button {:style {:width 120 :height 30} :on-click (fn [_] (rf/dispatch [:inc]))} "increment"]
    [:div {:style {:position "absolute" :top 0 :left 0 :width 120 :height 30
                  :background "#e0a458" :pointer-events "none"}}
     "click me"]]
   [:span.value {:style {:padding 8}} @(rf/subscribe [:count])]
   [:p {:style {:padding 8 :max-width 500}}
    "visibility:hidden proof: the (invisible) overlay below is painted "
    "directly on top of the second increment button, fully covering it. "
    "Previously visibility:hidden was never consulted by hit-test either, "
    "so a click here would hit the invisible overlay instead -- clicking "
    "anywhere in that area should still increment the second counter, "
    "since a visibility:hidden element must be fully transparent to "
    "pointer events, same as pointer-events:none."]
   [:div {:style {:position "relative" :width 120 :height 30}}
    [:button {:style {:width 120 :height 30} :on-click (fn [_] (rf/dispatch [:inc2]))} "increment 2"]
    [:div {:style {:position "absolute" :top 0 :left 0 :width 120 :height 30
                  :background "#e0a458" :visibility "hidden"}}
     "click me"]]
   [:span.value2 {:style {:padding 8}} @(rf/subscribe [:count2])]
   [:p {:style {:padding 8 :max-width 500}}
    "flex-wrap justify-content proof: three 140px boxes wrap onto two rows "
    "within this 300px-wide container (two fit per row, the third wraps). "
    "Previously flex-wrap:wrap hardcoded flex-start for main-axis packing "
    "regardless of justify-content, so every row packed flush left no "
    "matter what. Both rows below use justify-content:center, and must "
    "each center against their OWN row content width -- row 1 (two boxes, "
    "288px incl. gap) and row 2 (one box, 140px) get different, "
    "independently-computed offsets, not flush-left."]
   [:div {:style {:display "flex" :flex-wrap "wrap" :justify-content "center"
                  :width 300 :gap 8 :background "#1c2333"}}
    [:div {:style {:width 140 :height 40 :background "#5fb3d9"}} "A"]
    [:div {:style {:width 140 :height 40 :background "#5fb3d9"}} "B"]
    [:div {:style {:width 140 :height 40 :background "#5fb3d9"}} "C"]]
   [:p {:style {:padding 8 :max-width 500}}
    "justify-content:space-around/space-evenly proof: previously BOTH "
    "keywords had no branch in place-main-axis at all and silently "
    "packed flush left, identical to flex-start. space-around (row 1) "
    "gives each box a half-size gap at the outer edges, full-size gaps "
    "between boxes; space-evenly (row 2) uses the SAME-size gap "
    "everywhere, including the outer edges -- the visible difference "
    "in edge-gap width between the two rows below is the proof."]
   [:div {:style {:display "flex" :justify-content "space-around"
                  :width 460 :background "#1c2333" :margin-bottom 4}}
    [:div {:style {:width 100 :height 36 :background "#5fb3d9"}} "1"]
    [:div {:style {:width 100 :height 36 :background "#5fb3d9"}} "2"]
    [:div {:style {:width 100 :height 36 :background "#5fb3d9"}} "3"]]
   [:div {:style {:display "flex" :justify-content "space-evenly"
                  :width 460 :background "#1c2333"}}
    [:div {:style {:width 100 :height 36 :background "#79c99e"}} "1"]
    [:div {:style {:width 100 :height 36 :background "#79c99e"}} "2"]
    [:div {:style {:width 100 :height 36 :background "#79c99e"}} "3"]]])

(defn install-model! []
  (rf/clear!)
  (rf/reg-event-db :init (fn [_ _] {:count 0 :count2 0}))
  (rf/reg-event-db :inc (fn [db _] (update db :count inc)))
  (rf/reg-event-db :inc2 (fn [db _] (update db :count2 inc)))
  (rf/reg-sub :count (fn [db _] (:count db)))
  (rf/reg-sub :count2 (fn [db _] (:count2 db)))
  (rf/dispatch-sync [:init]))

(defn ^:export init! []
  (install-model!)
  (let [gl-canvas (.getElementById js/document "kotoba-gl")
        text-canvas (.getElementById js/document "kotoba-text")
        host (webgl/create-host! {:gl-canvas gl-canvas
                                  :text-canvas text-canvas
                                  :width 720
                                  :height 420})
        rt (runtime/mount! host app)]
    (reset! runtime-state rt)
    (webgl/install-pointer-events! host text-canvas
                                   (fn []
                                     (swap! runtime-state runtime/pump-events!)))))

(defn ^:export debug-snapshot []
  (let [rt @runtime-state]
    (clj->js (debug/snapshot {:backend "webgl"
                              :runtime rt
                              :host-state (some-> rt :host webgl/state)}))))

(defn ^:dev/after-load reload! []
  (when-let [{:keys [host]} @runtime-state]
    (swap! runtime-state (fn [_] (runtime/mount! host app)))))
