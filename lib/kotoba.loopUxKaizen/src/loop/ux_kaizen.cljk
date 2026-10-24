(ns loop.ux-kaizen
  "Pure contract for a continuous UX evaluation and improvement loop.

  Browser/model/process I/O belongs to host adapters. This namespace owns the
  scenario, evidence and gate semantics shared by local runners, GitHub
  Actions and agent skills."
  (:require [kotoba.lang.text :as str]))

(def scenario-schema "kotoba.loop.ux-kaizen.scenario.v0")
(def evidence-schema "kotoba.loop.ux-kaizen.evidence.v0")

(def phases [:build :audit :capture :journey :judge :decide])

(def required-persona-keys
  [:persona/id :persona/role :persona/context :persona/goals
   :persona/fears :persona/device])

(defn valid-persona? [persona]
  (and (map? persona)
       (every? #(contains? persona %) required-persona-keys)))

(defn valid-scenario? [{:keys [schema surface persona journeys gates]}]
  (and (= scenario-schema schema)
       (keyword? (:id surface))
       (pos-int? (get-in surface [:viewport :width]))
       (pos-int? (get-in surface [:viewport :height]))
       (valid-persona? persona)
       (vector? journeys)
       (every? #(and (keyword? (:id %)) (string? (:goal %))) journeys)
       (number? (:deterministic-min gates))
       (number? (:journey-pass-rate gates))))

(defn plan [scenario]
  (when-not (valid-scenario? scenario)
    (throw (ex-info "Invalid UX kaizen scenario" {:scenario scenario})))
  (mapv (fn [index phase]
          {:step/index index
           :step/phase phase
           :step/surface (get-in scenario [:surface :id])})
        (range)
        phases))

(defn evidence
  [{:keys [run-id surface phase status detail artifact metrics]}]
  (cond-> {:schema evidence-schema
           :run-id run-id
           :surface surface
           :phase phase
           :status status}
    (seq (str detail)) (assoc :detail detail)
    artifact (assoc :artifact artifact)
    metrics (assoc :metrics metrics)))

(defn gate
  "Aggregate deterministic, journey and persona evidence. Missing required
  evidence fails closed; a visual/persona judge is discovery evidence and is
  only required when :persona-axis-min is configured."
  [scenario evidence-items]
  (let [{:keys [deterministic-min journey-pass-rate persona-axis-min]} (:gates scenario)
        metric (fn [k] (some #(get-in % [:metrics k]) evidence-items))
        deterministic (metric :deterministic-score)
        journeys (metric :journey-pass-rate)
        persona (metric :persona-axis-min)
        checks (cond->
                 [{:id :deterministic
                   :passed? (and (number? deterministic)
                                 (>= deterministic deterministic-min))}
                  {:id :journeys
                   :passed? (and (number? journeys)
                                 (>= journeys journey-pass-rate))}]
                 persona-axis-min
                 (conj {:id :persona
                        :passed? (and (number? persona)
                                      (>= persona persona-axis-min))}))]
    {:schema "kotoba.loop.ux-kaizen.gate.v0"
     :surface (get-in scenario [:surface :id])
     :checks checks
     :passed? (every? :passed? checks)}))

(defn repo-kind [repo-name]
  (cond
    (str/starts-with? repo-name "loop-") :loop
    (str/starts-with? repo-name "skill-") :skill
    (str/starts-with? repo-name "action-") :action
    :else :library))
