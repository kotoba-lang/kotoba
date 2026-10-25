(ns kotoba.wasm.host.browser-events
  "Browser event adapters for retained canvas hosts.
   This namespace extracts DOM event data; retained.cljc owns event semantics."
  (:require [kotoba.wasm.host.retained :as retained]))

(defn- canvas-point [canvas event]
  (let [rect (.getBoundingClientRect canvas)]
    {:x (- (.-clientX event) (.-left rect))
     :y (- (.-clientY event) (.-top rect))}))

(defn- swap-queued! [state-atom f]
  (let [queued? (volatile! false)]
    (swap! state-atom
           (fn [state]
             (let [next-state (f state)]
               (when-not (identical? state next-state)
                 (vreset! queued? true))
               next-state)))
    @queued?))

(defn queue-hit-event! [host x y event-name extra]
  (swap-queued! (:state host)
                #(retained/queue-hit-event % x y event-name extra)))

(defn queue-focused-event! [host event-name extra]
  (swap-queued! (:state host)
                #(retained/queue-focused-event % event-name extra)))

(defn install-canvas-events! [host canvas pump!]
  (set! (.-tabIndex canvas) 0)
  (.addEventListener canvas "click"
                     (fn [event]
                       (.focus canvas)
                       (let [{:keys [x y]} (canvas-point canvas event)]
                         (when (queue-hit-event! host x y :click nil)
                           (pump!)))))
  (.addEventListener canvas "keydown"
                     (fn [event]
                       (when (queue-focused-event! host :key-down {:key (.-key event)})
                         (.preventDefault event)
                         (pump!)))))
