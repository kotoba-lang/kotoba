(ns simulated-user.live-smoke
  (:require [simulated-user.eval :as eval]
            [simulated-user.model :as model]
            [simulated-user.murakumo :as murakumo]
            [simulated-user.murakumo-host :as host]))

(def schema
  {:source :synthetic
   :order [:device]
   :dimensions {:device {:values [:mobile :desktop]}}})

(def task
  {:task/id :murakumo-live-smoke
   :environment :web
   :purpose :product-evaluation
   :decision-impact :none
   :prompt "Evaluate whether the fictional user would continue this completed flow."})

(def trace
  [{:event/index 0 :event/action :observe
    :event/target :checkout :event/outcome :visible}
   {:event/index 1 :event/action :click
    :event/target :continue-button :event/outcome :advanced}
   {:event/index 2 :event/action :finish
    :event/target :checkout :event/outcome :completed}])

(defn -main [& _]
  (let [url (System/getenv "MURAKUMO_LLM_URL")
        interact (murakumo/make-interact (host/make-chat {:url url}))
        persona (first (model/sample-cohort schema {:seed 11 :n 1}))
        result (eval/run-trial interact task persona {:interaction/trace trace})]
    (prn result)))
