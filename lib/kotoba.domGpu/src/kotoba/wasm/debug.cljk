(ns kotoba.wasm.debug
  "Runtime debug snapshots for kotoba WASM UI hosts.
   This stays pure so browser demos and JVM tests assert the same shape."
  (:require [kotoba.wasm.dom :as dom]))

(defn snapshot
  [{:keys [backend runtime host-state]}]
  (if-let [{:keys [document handlers]} runtime]
    {:mounted true
     :backend backend
     :root (:root document)
     :text (dom/text-content document)
     :node-count (count (:nodes document))
     :handler-count (count handlers)
     :draw-op-count (count (:draw-ops host-state))
     :event-queue-depth (count (:events host-state))}
    {:mounted false
     :backend backend}))
