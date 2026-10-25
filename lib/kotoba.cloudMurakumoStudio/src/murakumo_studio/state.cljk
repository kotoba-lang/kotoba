(ns murakumo-studio.state
  (:require [reagent.core :as r]))

(defonce state
  (r/atom
   {:tab :models
    :engine {:status :starting :error nil}   ; :starting :ready :error
    :models {:items [] :loading? false :error nil}
    :chat {:model nil :messages [] :input "" :busy? false :error nil :note nil}
    :download {:repo-id "" :file "" :busy? false :error nil :done nil
               :query "" :results [] :searching? false
               :selected-repo nil :hf-files [] :listing? false}
    ;; max-tokens default is deliberately small: kotoba-lang/inference's CPU
    ;; decode is currently ~10-30s/token even with KV-cache (no GPU path yet,
    ;; ADR-2607032700 Phase 2) — 256 would mean many minutes per reply.
    :settings {:threads 4 :context-length 2048 :temperature 0.7 :max-tokens 32}
    :fleet {:enabled? false :status nil :busy? false :error nil}}))

(defn set-tab! [tab]
  (swap! state assoc :tab tab))
