(ns browser.smoke-webgpu
  "WebGPU variant of `browser.smoke` -- same real `browser.session` +
   `browser.visual-smoke-model`, wired to a real `kotoba.wasm.host.webgpu`
   host instead. `create-host!` is async (WebGPU device request), unlike the
   WebGL host, so session construction happens inside its `.then`."
  (:require [browser.session :as session]
            [browser.visual-smoke-model :as model]
            [kotoba.wasm.host.webgpu :as webgpu]))

(defonce session-state (atom nil))

(defn fail!
  [message]
  (when-let [el (.getElementById js/document "status")]
    (set! (.-textContent el) message)))

(defn ^:export init!
  []
  (let [gpu-canvas (.getElementById js/document "kotoba-gpu")
        text-canvas (.getElementById js/document "kotoba-text")
        [width height] model/viewport]
    (-> (webgpu/create-host! {:gpu-canvas gpu-canvas
                              :text-canvas text-canvas
                              :width width
                              :height height
                              ;; see browser.smoke for why the host needs
                              ;; the theme and not only the session.
                              :theme model/theme})
        (.then
         (fn [host]
           (let [s (session/new-session {:host host
                                         :viewport model/viewport
                                         :theme model/theme
                                         :surface (model/surface-model)})
                 s (session/apply-surface-action! s (model/launch-action))
                 s (session/load-html! s model/page)]
             (reset! session-state s)
             (fail! "WebGPU host active"))))
        (.catch
         (fn [err]
           (js/console.error err)
           (fail! (str "WebGPU unavailable: " (.-message err))))))))
