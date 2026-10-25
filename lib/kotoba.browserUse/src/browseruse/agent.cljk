(ns browseruse.agent
  "browser-use agent loop on langgraph-clj:

      :agent → (tool calls?) → :tools → :agent → … → done/END

  The model sees the task plus the indexed-element page state; every
  action result re-embeds the fresh state. The loop ends when the
  model calls the `done` action (or stops calling tools / hits
  :max-steps).

  Datomic premise (ADR-0010): with a :history-conn every executed
  action is recorded as a datom — sessions become a queryable audit
  trail (\"every URL the agent visited\", \"all input_text actions
  yesterday\") instead of a log file."
  (:require [langgraph.graph :as g]
            [langchain.model :as model]
            [langchain.message :as msg]
            [langchain.tool :as tool]
            [langchain.db :as db]
            [browseruse.browser :as b]
            [browseruse.actions :as actions]
            [browseruse.guardrail :as guardrail]
            [browseruse.captcha :as captcha]
            [browseruse.history :as history]
            [browseruse.session :as session]))

(def default-settings
  {:max-steps 25 :max-actions-per-step 10 :max-action-retries 0
   :action-timeout-ms 120000 :allowed-domains [] :sensitive-data {}
   :output-validator nil :planner {:enabled? false}
   :vision {:enabled? false} :metadata {}
   ;; Opt-in preserves legacy behaviour. :human and :external are implemented
   ;; by browseruse.captcha without coupling the agent to a solver vendor.
   :captcha {:mode :disabled}})

(defn agent-settings
  "Normalize structured AgentSettings. Unknown keys are retained for forward
  compatibility; bounded numeric settings fail early."
  [settings]
  (let [s (merge default-settings (or settings {}))]
    (doseq [k [:max-steps :max-actions-per-step :action-timeout-ms]]
      (when-not (pos? (get s k))
        (throw (ex-info "browser-use: AgentSettings value must be positive" {:key k}))))
    (when (neg? (:max-action-retries s))
      (throw (ex-info "browser-use: retries cannot be negative" {})))
    (assoc s :captcha (merge (:captcha default-settings) (:captcha s)))))

(def default-system-prompt
  (str "You are a browser automation agent. You control a browser via tools.\n"
       "Interactive elements are shown as [index]<tag>text</tag>; refer to them by index.\n"
       "Work step by step toward the user's task. "
       "When the task is complete, call the `done` tool with the result."))

(def log-schema
  "Merge into your db schema for the action log."
  {:session/id     {:db/unique :db.unique/identity}
   :action/session {:db/valueType :db.type/ref}
   :action/step    {}
   :action/name    {}
   :action/input   {}    ; pr-str EDN
   :action/result  {}
   :action/url     {}
   :action/attempts {}
   :action/elapsed-ms {}
   :action/error {}})

(defn- log-action! [conn db-api session-id result]
  (let [{:keys [transact!]} db-api]
    (transact! conn
               [{:session/id session-id}
                {:action/session [:session/id session-id]
                 :action/step (:step result)
                 :action/name (:action result)
                 :action/input (pr-str (:input result))
                 :action/result (str (:output result))
                 :action/url (str (:url result))
                 :action/attempts (:attempts result)
                 :action/elapsed-ms (:elapsed-ms result)
                 :action/error (str (:error result))}])))

(defn build-agent
  "Compiles the agent graph.

  opts: {:model ChatModel  :browser IBrowser
         :actions [tool…]          ; default: actions/default-actions
         :system \"…\"             ; default: default-system-prompt
         :history-conn conn        ; optional — action log datoms
         :session-id \"…\"         ; action-log session (default \"default\")
         :db-api langchain.db/api
         :max-steps 25
         :compile-opts {…}}        ; extra langgraph compile opts"
  [{:keys [model browser actions system history-conn session-id db-api max-steps compile-opts
           settings session history]
    :or {db-api db/api session-id "default"}}]
  (let [settings (agent-settings (merge (or settings {})
                                        (when max-steps {:max-steps max-steps})))
        session (or session (session/create-session {:id session-id}))
        audit-settings (update settings :captcha captcha/public-settings)
        history (or history (atom (history/empty-history session-id audit-settings)))
        tools (conj (vec (or actions (actions/default-actions browser)))
                    actions/done-action)
        step-counter (atom 0)
        call-model
        (fn [{:keys [messages]}]
          (when-not (session/runnable? session)
            (throw (ex-info "browser-use: session is not running"
                            {:status (session/status session)})))
          (when-let [result (captcha/maybe-solve! (b/-state browser)
                                                   (assoc (:captcha settings)
                                                          :session session))]
            (when-not (= :solved (:status result))
              (throw (ex-info "browser-use: CAPTCHA awaits operator"
                              {:type :captcha/pending
                               :result (captcha/audit-result result)}))))
          {:messages [(model/-generate model
                                       (into [(msg/system (or system default-system-prompt))]
                                             messages)
                                       {:tools tools
                                        :metadata (merge (:metadata settings)
                                                         {:planner (:planner settings)
                                                          :vision (:vision settings)})})]})
        run-tools
        (fn [{:keys [messages]}]
          (let [calls (:tool-calls (msg/last-message messages))
                _ (when (> (count calls) (:max-actions-per-step settings))
                    (throw (ex-info "browser-use: max actions per step exceeded"
                                    {:limit (:max-actions-per-step settings)
                                     :count (count calls)})))
                outcome
                (reduce
                 (fn [{:keys [msgs] :as acc} {:keys [name] :as call}]
                   (session/hook! session :before-step {:call call :session session})
                   (let [step (swap! step-counter inc)
                         executed (try
                                    (guardrail/execute settings call #(tool/execute tools call))
                                    (catch #?(:clj Exception :cljs :default) e
                                      (session/hook! session :on-error
                                                     {:call call :error e :step step})
                                      (throw e)))
                         r (:value executed)
                         current-url (:url (b/-state browser))
                         _ (guardrail/assert-url! settings current-url)
                         action-result
                         (history/->ActionResult
                          step name
                          (guardrail/redact (:input call) (:sensitive-data settings))
                          (guardrail/redact (:content r) (:sensitive-data settings))
                          nil current-url (:attempts executed) (:elapsed-ms executed)
                          {:planner (:planner settings) :vision (:vision settings)})]
                     (swap! history history/append action-result)
                     (when history-conn
                       (log-action! history-conn db-api session-id action-result))
                     (session/hook! session :after-step action-result)
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
        (g/compile-graph (merge {:recursion-limit (:max-steps settings)} compile-opts)))))

(defn run
  "One-shot: builds the agent and runs a task. Returns
  {:result .. :done bool :messages [..] :steps n}.

  (run {:model m :browser b :task \"Find the pricing page\"
        :history-conn conn :session-id \"s1\"})"
  [{:keys [browser task run-opts session history session-id settings] :as opts}]
  (let [session (or session (session/create-session {:id (or session-id "default")}))
        settings (agent-settings (merge (or settings {})
                                        (when-let [n (:max-steps opts)] {:max-steps n})))
        audit-settings (update settings :captcha captcha/public-settings)
        history (or history (atom (history/empty-history (or session-id "default") audit-settings)))
        agent (build-agent (assoc opts :session session :history history :settings settings))
        first-msg (msg/user (str "Task: " task "\n\n"
                                 (b/state->prompt (b/-state browser))))
        out (g/run* agent {:messages [first-msg]} (or run-opts {}))]
    {:result (:result (:state out))
     :done (boolean (:done (:state out)))
     :messages (:messages (:state out))
     :steps (count (:events out))
     :session session
     :history @history
     :settings audit-settings}))
