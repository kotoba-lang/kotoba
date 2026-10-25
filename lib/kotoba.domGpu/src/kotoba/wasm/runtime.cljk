(ns kotoba.wasm.runtime
  "Mount/re-render loop for Reagent-style apps on the kotoba DOM host ABI."
  (:require [kotoba.wasm.abi :as abi]
            [kotoba.wasm.host :as host]
            [reagent.core :as r]))

(defn render-app [root]
  (r/render [root]))

(defn mount! [dom-host root]
  (let [{:keys [document handlers ops] :as rendered} (render-app root)]
    (host/commit! dom-host ops)
    {:host dom-host
     :root root
     :document document
     :handlers handlers
     :last-batch (abi/encode-batch ops)
     :rendered rendered}))

(defn rerender! [runtime]
  (let [{:keys [document handlers ops] :as rendered} (render-app (:root runtime))]
    (host/commit! (:host runtime) ops)
    (assoc runtime
           :document document
           :handlers handlers
           :last-batch (abi/encode-batch ops)
           :rendered rendered)))

(defn handle-event! [runtime event]
  (let [handler-id (abi/event-handler-id event)]
    (if-let [handler (get-in runtime [:handlers handler-id])]
      (do
        (handler (abi/host-event event))
        (rerender! runtime))
      runtime)))

(defn pump-events! [runtime]
  (loop [runtime runtime]
    (if-let [event (host/poll-host-event! (:host runtime))]
      (recur (handle-event! runtime event))
      runtime)))
