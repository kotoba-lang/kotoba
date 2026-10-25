(ns kotoba.wasm.demo-webgpu
  "WebGPU variant of the kotoba:dom host demo."
  (:require [kotoba.wasm.debug :as debug]
            [kotoba.wasm.host.webgpu :as webgpu]
            [kotoba.wasm.runtime :as runtime]
            [re-frame.core :as rf]))

(defonce runtime-state (atom nil))

(defn app []
  [:main.demo {:style {:padding 18 :width 620 :background "#121724"}}
   [:h1 "kotoba DOM on WebGPU"]
   [:p "Same Reagent/re-frame style UI, rendered through the WebGPU host."]
   [:button {:on-click (fn [_] (rf/dispatch [:inc]))} "increment"]
   [:span.value {:style {:padding 8}} @(rf/subscribe [:count])]
   [:p {:style {:margin-top 8}}
    "content-height proof: the tall box below extends past the host's "
    "initial 420px :height -- previously this backend never auto-grew "
    "the canvas to fit real content (unlike the WebGL host), so "
    "everything past 420px silently painted off-canvas, invisible."]
   [:div {:style {:height 500 :margin-top 8 :background "#4fd1c5"}}
    [:p {:style {:padding 8}} "tall-content-marker (top)"]]
   [:div#tall-content-bottom-marker {:style {:padding 8}}
    "tall-content-marker (bottom -- visible only once auto-grow works)"]])

(defn install-model! []
  (rf/clear!)
  (rf/reg-event-db :init (fn [_ _] {:count 0}))
  (rf/reg-event-db :inc (fn [db _] (update db :count inc)))
  (rf/reg-sub :count (fn [db _] (:count db)))
  (rf/dispatch-sync [:init]))

(defn fail! [message]
  (when-let [el (.getElementById js/document "status")]
    (set! (.-textContent el) message)))

(defn ^:export init! []
  (install-model!)
  (let [gpu-canvas (.getElementById js/document "kotoba-gpu")
        text-canvas (.getElementById js/document "kotoba-text")]
    (-> (webgpu/create-host! {:gpu-canvas gpu-canvas
                              :text-canvas text-canvas
                              :width 720
                              :height 420})
        (.then
         (fn [host]
           (let [rt (runtime/mount! host app)]
             (reset! runtime-state rt)
             (webgpu/install-pointer-events! host text-canvas
                                             (fn []
                                               (swap! runtime-state runtime/pump-events!)))
             (fail! "WebGPU host active"))))
        (.catch
         (fn [err]
           (js/console.error err)
           (fail! (str "WebGPU unavailable: " (.-message err))))))))

(defn ^:export debug-snapshot []
  (let [rt @runtime-state]
    (clj->js (debug/snapshot {:backend "webgpu"
                              :runtime rt
                              :host-state (some-> rt :host webgpu/state)}))))

(defn ^:dev/after-load reload! []
  (when-let [{:keys [host]} @runtime-state]
    (swap! runtime-state (fn [_] (runtime/mount! host app)))))
