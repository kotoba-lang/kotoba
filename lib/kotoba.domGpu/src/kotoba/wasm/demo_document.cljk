(ns kotoba.wasm.demo-document
  "Reference *document* rendering demo for kotoba WASM UI.

   Unlike kotoba.wasm.demo (a synthetic reagent/re-frame counter UI diffed
   through kotoba.wasm.runtime/mount!), this demo proves the real
   HTML -> CSS cascade -> layout -> paint pipeline end to end:

     htmldom.core/parse-into-document  (HTML text -> kotoba.wasm.dom document)
     -> cssom.core/apply-cascade       (+ CSS rules -> cascaded document)
     -> kotoba.wasm.dom/tree           (document -> retained-shaped tree)
     -> cssom.layout/draw-ops          (tree -> rect/text/node draw ops)
     -> kotoba.wasm.host.webgl         (draw ops -> real WebGL/canvas pixels)

   A cascaded document is already a *complete* retained tree, not a UI tree
   that needs virtual-DOM diffing, so this intentionally skips
   kotoba.wasm.runtime/mount! and the ABI op-batch replay in
   kotoba.wasm.host/commit!. Those exist to replay *incremental* changes
   emitted by re-rendering a reagent app; here there is only one document,
   rendered once.

   The integration point is kotoba.wasm.host.webgl/create-host!'s returned
   :state atom: its shape (a map of :nodes/:root/:width/:height/...) is the
   exact retained-tree shape kotoba.wasm.host.retained/apply-op builds one
   ABI op at a time -- and a kotoba.wasm.dom document's own :nodes/:root are
   already in that shape (see kotoba.wasm.dom/create-element vs.
   kotoba.wasm.host.retained/apply-op's :create-element case). So the
   cascaded document's :nodes/:root can be installed into the host state
   directly, and the existing (unmodified) private render!/present-webgl!
   in kotoba.wasm.host.webgl -- which internally calls
   kotoba.wasm.host.retained/draw-ops on that same state -- paints it for
   real, through kotoba.wasm.host/present-host!."
  (:require [kotoba.wasm.host :as host]
            [kotoba.wasm.host.webgl :as webgl]
            [kotoba.wasm.dom :as dom]
            [htmldom.core :as htmldom]
            [cssom.core :as cssom]
            [cssom.layout :as layout]))

(defonce document-state (atom nil))

(def sample-html
  "<main style=\"padding: 8px\"><h1>Kotoba Browser</h1><p style=\"color: #4fb3a6\">A real document, rendered.</p></main>")

(def sample-css
  "main { background: #121724; } h1 { color: #e6ebf5; }")

(defn build-cascaded-document
  "HTML + CSS text -> a real, cascaded kotoba.wasm.dom document."
  [html css]
  (let [parsed (htmldom/parse-into-document html)
        rules (cssom/parse-rules css)]
    (cssom/apply-cascade parsed rules)))

(defn ^:export init! []
  (let [cascaded (build-cascaded-document sample-html sample-css)
        gl-canvas (.getElementById js/document "kotoba-gl")
        text-canvas (.getElementById js/document "kotoba-text")
        the-host (webgl/create-host! {:gl-canvas gl-canvas
                                      :text-canvas text-canvas
                                      :width 720
                                      :height 420})
        ops (layout/draw-ops (dom/tree cascaded) {:width 720})]
    (js/console.log "kotoba.wasm.demo-document draw-ops:" (pr-str ops))
    ;; Install the cascaded document's retained-shaped tree straight into the
    ;; webgl host's state, then let the existing host paint it -- no
    ;; reagent/re-frame vdom, no ABI op-batch replay needed.
    (swap! (:state the-host) merge {:nodes (:nodes cascaded) :root (:root cascaded)})
    (host/present-host! the-host)
    (reset! document-state {:host the-host :document cascaded :draw-ops ops})))

(defn ^:export debug-snapshot []
  (some-> @document-state :draw-ops clj->js))

(defn ^:dev/after-load reload! []
  (when-let [{:keys [host]} @document-state]
    (host/present-host! host)))
