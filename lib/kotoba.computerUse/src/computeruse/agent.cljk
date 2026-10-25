(ns computeruse.agent
  "Computer-use sampling loop on langgraph-clj:

      :agent → (tool calls?) → :tools → :agent → … → done/END

  The model drives the computer tool (screenshot / click / type / …)
  until it calls `done` (or stops calling tools / hits :max-steps) —
  the loop of Anthropic's computer-use reference implementation.

  Datomic premise (ADR-0010): with a :history-conn every action is a
  datom — sessions are a queryable audit trail (\"every click in
  session s1\", \"all sessions that pressed ctrl+s\")."
  (:require [langgraph.graph :as g]
            [langchain.model :as model]
            [langchain.message :as msg]
            [langchain.tool :as tool]
            [langchain.db :as db]
            [computeruse.tool :as ctool]
            [computeruse.hil :as hil]))

(def default-system-prompt
  (str "You are a computer-use agent controlling a desktop via the `computer` tool.\n"
       "Take a screenshot first to see the screen. Click, type and press keys to "
       "work toward the user's task, taking screenshots to verify the results.\n"
       "When the task is complete, call the `done` tool with the result."))

(def done-tool
  {:name "done"
   :description "Call when the task is complete. Provide the final answer/result as text."
   :schema {:type "object"
            :properties {:text {:type "string"}
                         :success {:type "boolean"}}
            :required ["text"]}
   :fn (fn [{:keys [text]}] text)})

(def log-schema
  "Merge into your db schema for the action log."
  {:session/id     {:db/unique :db.unique/identity}
   :caction/session {:db/valueType :db.type/ref}
   :caction/step   {}
   :caction/tool   {}
   :caction/action {}
   :caction/input  {}    ; pr-str EDN
   :caction/result {}})

(defn- log-action! [conn db-api session-id step {:keys [name input]} result]
  (let [{:keys [transact!]} db-api]
    (transact! conn
               [{:session/id session-id}
                {:caction/session [:session/id session-id]
                 :caction/step step
                 :caction/tool name
                 :caction/action (str (:action input))
                 :caction/input (pr-str input)
                 :caction/result (str result)}])))

(defn build-agent
  "Compiles the agent graph.

  opts: {:model ChatModel  :computer IComputer
         :display {:width 1280 :height 800}
         :vault IVault             ; optional — enables `type_secret` credential injection
         :approval-prompt IHumanApproval ; optional — enables request_human_approval
         :tools [tool…]            ; extra tools alongside `computer`
         :system \"…\"
         :history-conn conn        ; optional — action log datoms
         :session-id \"…\"
         :db-api langchain.db/api
         :max-steps 25
         :compile-opts {…}}"
  [{:keys [model computer display vault approval-prompt tools system history-conn session-id db-api
           max-steps compile-opts]
    :or {db-api db/api max-steps 25 session-id "default"}}]
  (let [all-tools (cond-> [(ctool/computer-tool computer (assoc display :vault vault))
                           done-tool]
                    approval-prompt (conj (hil/approval-tool approval-prompt))
                    true (into tools))
        step-counter (atom 0)
        call-model
        (fn [{:keys [messages]}]
          {:messages [(model/-generate model
                                       (into [(msg/system (or system default-system-prompt))]
                                             messages)
                                       {:tools all-tools})]})
        run-tools
        (fn [{:keys [messages]}]
          (let [calls (:tool-calls (msg/last-message messages))
                outcome
                (reduce
                 (fn [{:keys [msgs] :as acc} {:keys [name] :as call}]
                   (let [r (tool/execute all-tools call)
                         step (swap! step-counter inc)]
                     (when history-conn
                       (log-action! history-conn db-api session-id step call (:content r)))
                     (cond-> (assoc acc :msgs (conj msgs r))
                       (= "done" name) (assoc :done true :result (:text (:input call))))))
                 {:msgs []}
                 calls)]
            (cond-> {:messages (:msgs outcome)}
              (:done outcome) (assoc :done true :result (:result outcome)))))]
    (-> (g/state-graph {:channels {:messages {:reducer (fnil into []) :default []}
                                   :done {:default false}
                                   :result {}}})
        (g/add-node :agent call-model)
        (g/add-node :tools run-tools)
        (g/set-entry-point :agent)
        (g/add-conditional-edges :agent
                                 (fn [{:keys [messages]}]
                                   (if (msg/tool-calls (msg/last-message messages))
                                     :tools
                                     g/END)))
        (g/add-conditional-edges :tools
                                 (fn [{:keys [done]}] (if done g/END :agent)))
        (g/compile-graph (merge {:recursion-limit max-steps} compile-opts)))))

(defn run
  "One-shot: builds the agent and runs a task. Returns
  {:result .. :done bool :messages [..] :steps n}."
  [{:keys [task run-opts] :as opts}]
  (let [agent (build-agent opts)
        out (g/run* agent {:messages [(msg/user (str "Task: " task))]}
                    (or run-opts {}))]
    {:result (:result (:state out))
     :done (boolean (:done (:state out)))
     :messages (:messages (:state out))
     :steps (count (:events out))}))
