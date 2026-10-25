(ns browseragent.supervisor
  "Mixture-of-Agents supervisor as a langgraph StateGraph:

      :delegate → (more steps?) → :delegate → … → :aggregate → END

  For each plan step it routes to a sub-agent (the planner's
  `:assignee`, or an injected `:router` override — cheap model routes,
  strong model handles the hard step), runs it, and records the
  decision + outcome as a `:deleg/*` datom. `:aggregate` synthesizes
  the step results into the final answer, optionally cross-checking
  with an `:aggregator-model` (the MoA factuality pass).

  State channels:
    :plan    the numbered steps (last-write-wins; replan can swap it)
    :cursor  index of the next step
    :results [{:step :assignee :result} …]  (accumulated)
    :done / :result  terminal answer"
  (:require [browseragent.fleet :as fleet]
            [browseragent.memory :as mem]
            [browseragent.planner :as planner]
            [kotoba.lang.text :as str]
            [langgraph.graph :as g]
            [langchain.message :as msg]
            [langchain.model :as model]))

(defn- aggregate-text [task results aggregator-model]
  (let [bullets (->> results
                     (map (fn [{:keys [step assignee result]}]
                            (str "- [" step " " (name assignee) "] " result)))
                     (str/join "\n"))]
    (if aggregator-model
      (msg/text (model/-generate
                 aggregator-model
                 [(msg/system "Synthesize the sub-agent results into one final answer. Resolve any conflicts; be concise.")
                  (msg/user (str "Task: " task "\n\nResults:\n" bullets))]
                 {}))
      (str "Task: " task "\n\n" bullets))))

(defn build-supervisor
  "Compile the supervisor graph over a fleet + ctx.
  ctx carries models, the owned browser, db handles and host fns."
  [{:keys [fleet ctx task router aggregator-model replan-fn]
    :or {fleet fleet/default-fleet}}]
  (let [{:keys [conn db-api task-id]} ctx
        delegate
        (fn [{:keys [plan cursor results]}]
          (let [step0 (nth plan cursor)
                assignee (if router (router step0 ctx) (:assignee step0))
                step (assoc step0 :assignee assignee)]
            (planner/mark-step! conn db-api task-id (:step step) :doing)
            (let [{:keys [result]} (fleet/dispatch fleet step ctx)]
              (mem/record-delegation! conn db-api task-id
                                      {:step (:step step) :agent assignee
                                       :model (get-in ctx [:models assignee])
                                       :goal (:goal step) :result result})
              (planner/mark-step! conn db-api task-id (:step step) :done)
              ;; replan after the step if a replan-fn is supplied
              (let [plan' (planner/replan {:replan-fn replan-fn :task task
                                           :plan plan :cursor (inc cursor)
                                           :results (conj results {:step (:step step)
                                                                   :assignee assignee
                                                                   :result result})})]
                {:plan plan'
                 :cursor (inc cursor)
                 :results [{:step (:step step) :assignee assignee :result result}]}))))
        aggregate
        (fn [{:keys [results]}]
          {:done true
           :result (aggregate-text task results aggregator-model)})]
    (-> (g/state-graph
         {:channels {:plan    {:default []}
                     :cursor  {:default 0}
                     :results {:reducer (fnil into []) :default []}
                     :done    {:default false}
                     :result  {}}})
        (g/add-node :delegate delegate)
        (g/add-node :aggregate aggregate)
        (g/set-entry-point :delegate)
        (g/add-conditional-edges
         :delegate
         (fn [{:keys [plan cursor]}]
           (if (< cursor (count plan)) :delegate :aggregate)))
        (g/add-edge :aggregate g/END)
        (g/compile-graph {:recursion-limit (+ 3 (* 2 (max 1 (count (:plan ctx)))))}))))

(defn run-supervisor
  "Execute a plan through the MoA supervisor. Returns
  {:result :results :plan}."
  [{:keys [plan] :as opts}]
  (let [graph (build-supervisor (update opts :ctx assoc :plan plan))
        out (g/invoke graph {:plan plan :cursor 0})]
    {:result (:result out)
     :results (:results out)
     :plan plan}))
