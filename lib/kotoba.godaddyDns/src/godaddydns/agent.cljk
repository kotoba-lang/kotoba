(ns godaddydns.agent
  "GoDaddy DNS management agent on langgraph-clj:

      :agent → (tool calls?) → :tools → :agent → … → done/END

  The model drives the DNS tools (list_domains / list_records /
  upsert_record / delete_record) until it calls `done` (or stops calling
  tools / hits :max-steps).

  Two safety properties, on by default:
  - **dry-run** — write tools plan instead of mutating; the planned
    changes come back in :plan and nothing is applied. Pass :dry-run
    false to commit.
  - **audit log** — with a :history-conn every tool call becomes a datom
    (a queryable trail: \"every record changed in session s1\", \"all
    sessions that touched example.com\")."
  (:require [langgraph.graph :as g]
            [langchain.model :as model]
            [langchain.message :as msg]
            [langchain.tool :as tool]
            [langchain.db :as db]
            [godaddydns.tool :as dtool]))

(defn default-system-prompt [dry-run?]
  (str "You are a DNS management agent for GoDaddy-hosted domains, driving "
       "the list_domains / list_records / upsert_record / delete_record tools.\n"
       "Workflow: ALWAYS call list_records first to inspect the current state "
       "before proposing any change. Make the smallest change that satisfies "
       "the task. A host name of '@' is the zone apex.\n"
       (if dry-run?
         (str "DRY-RUN MODE: write tools (upsert_record/delete_record) only "
              "PLAN changes — nothing is actually applied. Describe the plan "
              "and call `done` summarizing what WOULD change.\n")
         (str "LIVE MODE: write tools apply changes immediately to real DNS. "
              "Be careful and minimal.\n"))
       "When finished, call the `done` tool with a concise summary."))

(def done-tool
  {:name "done"
   :description "Call when the task is complete. Provide the final summary as text."
   :schema {:type "object"
            :properties {:text {:type "string"}
                         :success {:type "boolean"}}
            :required ["text"]}
   :fn (fn [{:keys [text]}] text)})

(def log-schema
  "Merge into your db schema for the DNS action log."
  {:session/id      {:db/unique :db.unique/identity}
   :dnsaction/session {:db/valueType :db.type/ref}
   :dnsaction/step   {}
   :dnsaction/tool   {}
   :dnsaction/domain {}
   :dnsaction/record {}    ; "TYPE name" of the affected record (nil for reads)
   :dnsaction/input  {}    ; pr-str EDN of tool input
   :dnsaction/result {}
   :dnsaction/applied? {}})

(defn- log-action! [conn db-api session-id step {:keys [name input]} result dry-run?]
  (let [{:keys [transact!]} db-api
        write? (contains? dtool/write-tools name)]
    (transact! conn
               [{:session/id session-id}
                {:dnsaction/session [:session/id session-id]
                 :dnsaction/step step
                 :dnsaction/tool name
                 :dnsaction/domain (str (:domain input))
                 :dnsaction/record (when (and (:type input) (:name input))
                                     (str (:type input) " " (:name input)))
                 :dnsaction/input (pr-str input)
                 :dnsaction/result (str result)
                 :dnsaction/applied? (boolean (and write? (not dry-run?)))}])))

(defn build-agent
  "Compiles the agent graph.

  opts: {:model ChatModel   :dns IDns
         :dry-run true       ; plan-only writes (default true)
         :tools [tool…]      ; extra tools alongside the DNS tools
         :system \"…\"
         :history-conn conn  ; optional — action-log datoms
         :session-id \"…\"
         :db-api langchain.db/api
         :max-steps 25
         :plan-atom (atom [])  ; planned writes accumulate here
         :compile-opts {…}}"
  [{:keys [model dns dry-run tools system history-conn session-id db-api
           max-steps compile-opts plan-atom]
    :or {db-api db/api max-steps 25 session-id "default" dry-run true}}]
  (let [plan-atom (or plan-atom (atom []))
        all-tools (into (conj (dtool/dns-tools dns dry-run plan-atom) done-tool)
                        tools)
        step-counter (atom 0)
        call-model
        (fn [{:keys [messages]}]
          {:messages [(model/-generate model
                                       (into [(msg/system (or system (default-system-prompt dry-run)))]
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
                       (log-action! history-conn db-api session-id step call
                                    (:content r) dry-run))
                     (cond-> (assoc acc :msgs (conj msgs r))
                       (= "done" name) (assoc :done true :result (:text (:input call))))))
                 {:msgs []}
                 calls)]
            (cond-> {:messages (:msgs outcome)}
              (:done outcome) (assoc :done true :result (:result outcome)))))]
    {:plan-atom plan-atom
     :graph
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
         (g/compile-graph (merge {:recursion-limit max-steps} compile-opts)))}))

(defn run
  "One-shot: builds the agent and runs a task. Returns
  {:result .. :done bool :applied? bool :plan [change…] :messages [..] :steps n}.

  In dry-run (default) :plan holds the changes that WOULD be made and
  :applied? is false. With :dry-run false, writes are applied and :plan
  records what was applied."
  [{:keys [task run-opts dry-run] :or {dry-run true} :as opts}]
  (let [{:keys [graph plan-atom]} (build-agent opts)
        out (g/run* graph {:messages [(msg/user (str "Task: " task))]}
                    (or run-opts {}))]
    {:result (:result (:state out))
     :done (boolean (:done (:state out)))
     :applied? (not dry-run)
     :plan @plan-atom
     :messages (:messages (:state out))
     :steps (count (:events out))}))
