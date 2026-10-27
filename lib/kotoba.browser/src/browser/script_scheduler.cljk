(ns browser.script-scheduler
  "Host-side scheduling bridge for async page script engine lifecycle."
  (:require [browser.session :as session]))

#?(:cljs
   (defn promise-like?
     [x]
     (and x (fn? (.-then x)))))

#?(:clj
   (defn promise-like?
     [_]
     false))

(defn- error-value
  [error]
  #?(:cljs (or (.-message error) error)
     :clj error))

(defn complete!
  [session-atom completion]
  (swap! session-atom session/complete-script-engine-start! completion))

(defn fail!
  [session-atom failure]
  (swap! session-atom session/fail-script-engine-start! failure))

(defn abort!
  ([session-atom]
   (abort! session-atom :navigation/abort))
  ([session-atom reason]
   (swap! session-atom session/abort-script-engine-start! reason)))

(defn start!
  "Begin script engine startup and wire completion into `session-atom`.

  If the engine factory returns a Promise in ClojureScript, completion is applied
  when the host promise settles. If the session navigates or aborts meanwhile,
  session generation checks dispose the stale engine instead of adopting it."
  [session-atom]
  (let [{:keys [session token generation engine-or-promise]}
        (session/begin-script-engine-start! @session-atom)]
    (reset! session-atom session)
    (if (promise-like? engine-or-promise)
      (let [scheduled #?(:cljs
                         (.then engine-or-promise
                                (fn [engine]
                                  (complete! session-atom {:token token
                                                           :generation generation
                                                           :engine engine}))
                                (fn [error]
                                  (fail! session-atom {:token token
                                                       :generation generation
                                                       :error (error-value error)})))
                         :clj nil)]
        (cond-> {:script-scheduler/status :pending
                 :script-engine/token token
                 :page/generation generation}
          scheduled (assoc :script-scheduler/promise scheduled)))
      (do
        (complete! session-atom {:token token
                                 :generation generation
                                 :engine engine-or-promise})
        {:script-scheduler/status :ready
         :script-engine/token token
         :page/generation generation}))))
