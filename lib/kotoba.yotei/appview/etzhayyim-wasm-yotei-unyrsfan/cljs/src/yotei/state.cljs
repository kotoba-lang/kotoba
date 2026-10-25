(ns yotei.state
  (:require [reagent.core :as reagent]))

;; App state for the yotei appview (calendar / booking / events).
(defonce app
  (reagent/atom
   {:route :calendar
    ;; calendar view
    :calendar-id ""
    :availability []
    :events []
    :week-offset 0
    :loading false
    ;; booking form
    :requester-did ""
    :duration-min 30
    :message ""
    :submitting false
    :result ""
    :bookings []
    ;; events view
    :error nil}))

(defn set-val [k v]
  (swap! app assoc k v))

(defn- json->clj [j]
  (let [parsed (js->clj j :keywordize-keys true)]
    parsed))

;; XRPC helper — mirrors svelte App.svelte xrpc(): POST /xrpc/{nsid}.
;; NB: no thread macros mixing var-arg fns (js->clj) — bind with let.
(defn xrpc [nsid params on-ok]
  (let [opts #js {:method "POST"
                  :headers #js {"Content-Type" "application/json"}
                  :body (js/JSON.stringify (clj->js params))}]
    (-> (js/fetch (str "/xrpc/" nsid) opts)
        (.then (fn [resp] (.json resp)))
        (.then (fn [json-body]
                 (on-ok (json->clj json-body))))
        (.catch (fn [err]
                  (set-val :error (.-message err)))))))
