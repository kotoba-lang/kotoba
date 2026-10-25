(ns browseragent.events
  "UI-facing event projection — shared `.cljc` so the ClojureScript
  front-end and the server format the run the same way. Turns a
  finished run (plan + delegations + results) into a flat, renderable
  event stream for the plan tree / delegation feed."
  (:require [kotoba.lang.text :as str]))

(defn plan-events [plan]
  (for [{:keys [step goal assignee]} plan]
    {:channel :plan :kind :step :step step :goal goal :assignee assignee}))

(defn result-events [results]
  (for [{:keys [step assignee result]} results]
    {:channel :delegation :kind :result :step step :assignee assignee
     :result result}))

(defn run->events
  "Flatten a run map into an ordered event stream for the UI."
  [{:keys [plan results result]}]
  (concat (plan-events plan)
          (result-events results)
          [{:channel :final :kind :answer :result result}]))

(defn render-text
  "Plain-text projection (terminal / logs / quick check)."
  [run]
  (str/join "\n"
            (for [{:keys [channel kind step assignee goal result]} (run->events run)]
              (case channel
                :plan       (str "PLAN " step " → " (name assignee) ": " goal)
                :delegation (str "DONE " step " [" (name assignee) "] " result)
                :final      (str "\nANSWER:\n" result)
                (str channel " " kind)))))
