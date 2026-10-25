(ns kotoba-code.ink-main
  (:require [kotoba.lang.text :as str]
            [kotoba-code.composer-input :refer [composer-input]]
            [kotoba-code.ink-runtime :as runtime]
            [kotoba-code.slash-commands :as commands]
            [kotoba-code.ui-state :as state]
            ["ink" :refer [Box Text render useApp useInput useStdout]]
            ["react" :as react]))

(defn el [component props & children]
  (apply react/createElement component (clj->js props) children))

(defn message-view [props]
  (let [role (keyword (.-role props))
        text (.-text props)]
    (el Box {:flexDirection "row" :marginBottom 1}
      (el Text {:color (case role :user "cyan" :assistant "green" "yellow")
                :bold true}
          (case role :user "❯ " :assistant "● " "◆ "))
      (el Text {:wrap "wrap"} text))))

(defn tool-view [props]
  (let [name (.-name props)
        status (keyword (.-status props))
        summary (.-summary props)]
    (el Box {:flexDirection "row" :marginLeft 2}
      (el Text {:color (if (= status :working) "yellow" "gray")}
          (if (= status :working) "◌ " "✓ "))
      (el Text {:dimColor (= status :done)}
          (str name (when (seq summary) (str "  " summary)))))))

(defn app []
  (let [[ui-state dispatch] (react/useReducer state/reduce-event state/initial-state)
        [input set-input] (react/useState "")
        [selected-model set-selected-model] (react/useState (runtime/model-id))
        [agents set-agents] (react/useState [])
        child-ref (react/useRef nil)
        agent-children (react/useRef #js {})
        stdout (.-stdout (useStdout))
        exit (.-exit (useApp))
        working? (= :working (:status ui-state))
        done! #(set! (.-current child-ref) nil)
        select-model! (fn [model]
                        (set-selected-model model)
                        (dispatch {:event/type :system/message
                                   :text (str "Model changed to " model ".")}))
        run-command! (fn [args]
                       (set! (.-current child-ref)
                             (runtime/start-command!
                              {:app-dir (runtime/app-dir) :args args
                               :emit! dispatch :on-exit! done!})))
        update-agent! (fn [id f]
                        (set-agents
                         (fn [current]
                           (mapv #(if (= id (:id %)) (f %) %) current))))
        agents-summary (fn []
                         (if (seq agents)
                           (str/join
                            "\n"
                            (map #(str (:id %) "  " (name (:status %))
                                       "  " (:task %))
                                 agents))
                           "No background agents. Start one with /subtask <task>."))
        launch-agent! (fn [id task agent-root read-only?]
                        (update-agent! id #(assoc % :status :running
                                                  :root agent-root))
                        (aset (.-current agent-children) id
                              (runtime/start-subtask!
                               {:app-dir (runtime/app-dir)
                                :root agent-root :read-only? read-only?
                                :model selected-model :id id :text task
                                :on-event!
                                (fn [event]
                                  (case (:event/type event)
                                    :tool/started
                                    (update-agent! id
                                                   #(assoc % :current-tool
                                                           (:name event)))
                                    :tool/completed
                                    (update-agent! id
                                                   #(-> %
                                                        (dissoc :current-tool)
                                                        (update :tools conj
                                                                (:name event))))
                                    nil))
                                :on-done!
                                (fn [result]
                                  (js-delete (.-current agent-children) id)
                                  (update-agent! id #(merge % result
                                                            {:current-tool nil}))
                                  (dispatch
                                   {:event/type :system/message
                                    :text (str "Background agent " id " "
                                               (name (:status result))
                                               ". Use /agents " id
                                               " for details.")}))})))
        start-subtask! (fn [task writable?]
                         (let [id (subs (str (random-uuid)) 0 8)
                               entry {:id id
                                      :status (if writable? :preparing :running)
                                      :mode (if writable? :worktree :read-only)
                                      :task task :model selected-model :tools []}]
                           (set-agents #(conj % entry))
                           (if writable?
                             (runtime/create-worktree!
                              {:root (runtime/project-root) :id id
                               :on-done!
                               (fn [{:keys [ok? path error]}]
                                 (if ok?
                                   (do
                                     (update-agent! id #(assoc % :worktree path))
                                     (launch-agent! id task path false))
                                   (do
                                     (update-agent! id
                                                    #(assoc % :status :failed
                                                              :error error))
                                     (dispatch
                                      {:event/type :system/message
                                       :text (str "Could not create worktree for "
                                                  id ": " error)}))))})
                             (launch-agent! id task (runtime/project-root) true))
                           (dispatch
                            {:event/type :system/message
                             :text (str (if writable?
                                          "Preparing isolated write agent "
                                          "Started background agent ")
                                        id " (" (if writable?
                                                  "git worktree"
                                                  "read-only")
                                        ", " selected-model ").")})))
        submit! (fn [value]
                  (let [text (str/trim value)]
                    (when (seq text)
                      (let [{:keys [command args]} (commands/parse-command text)
                            arg (first args)]
                        (cond
                          (#{"exit" "quit" "/exit" "/quit"} text) (exit)
                          (= command "/help")
                          (dispatch {:event/type :system/message :text commands/help-text})
                          (= command "/clear")
                          (dispatch {:event/type :conversation/cleared})
                          (= command "/model")
                          (if arg (select-model! arg)
                              (dispatch {:event/type :system/message
                                         :text (str "Current model: " selected-model)}))
                          (= command "/codex")
                          (select-model! (str "codex:" (or arg "")))
                          (= command "/claude")
                          (select-model! (str "claude:" (or arg "sonnet")))
                          (= command "/openrouter")
                          (select-model! (or arg "z-ai/glm-5.2"))
                          (= command "/resume")
                          (do
                            (dispatch {:event/type :turn/submitted :text text})
                            (set! (.-current child-ref)
                                  (runtime/start-control!
                                   {:app-dir (runtime/app-dir)
                                    :root (runtime/project-root)
                                    :action "--resume" :emit! dispatch
                                    :on-exit! done!})))
                          (= command "/status")
                          (do (dispatch {:event/type :turn/submitted :text text})
                              (run-command! ["--status" (runtime/project-root)]))
                          (= command "/doctor")
                          (do (dispatch {:event/type :turn/submitted :text text})
                              (run-command! ["--doctor" (runtime/project-root)
                                             selected-model]))
                          (= command "/loop")
                          (let [action (or arg "status")
                                reason (str/join " " (rest args))]
                            (dispatch {:event/type :turn/submitted :text text})
                            (case action
                              "resume"
                              (set! (.-current child-ref)
                                    (runtime/start-control!
                                     {:app-dir (runtime/app-dir)
                                      :root (runtime/project-root)
                                      :action "--resume" :emit! dispatch
                                      :on-exit! done!}))
                              "stop"
                              (run-command! (cond-> ["--stop"
                                                    (runtime/project-root)
                                                    selected-model]
                                             (seq reason) (conj reason)))
                              "reset"
                              (run-command! (cond-> ["--reset-budget"
                                                    (runtime/project-root)
                                                    selected-model]
                                             (seq reason) (conj reason)))
                              "status"
                              (run-command! ["--budget"
                                             (runtime/project-root)
                                             selected-model])
                              "budget"
                              (run-command! ["--budget"
                                             (runtime/project-root)
                                             selected-model])
                              (dispatch {:event/type :turn/failed
                                         :message (str "Unknown /loop action: "
                                                       action)})))
                          (= command "/subtask")
                          (if (seq args)
                            (let [writable? (= "--write" arg)
                                  task-args (if writable? (rest args) args)]
                              (if (seq task-args)
                                (start-subtask! (str/join " " task-args)
                                                writable?)
                                (dispatch {:event/type :system/message
                                           :text "Usage: /subtask [--write] <task>"})))
                            (dispatch {:event/type :system/message
                                       :text "Usage: /subtask [--write] <task>"}))
                          (= command "/agents")
                          (cond
                            (nil? arg)
                            (dispatch {:event/type :system/message
                                       :text (agents-summary)})

                            (= arg "cancel")
                            (let [id (second args)
                                  child (when id
                                          (aget (.-current agent-children) id))]
                              (if child
                                (do (runtime/kill! child)
                                    (dispatch {:event/type :system/message
                                               :text (str "Cancelling agent " id
                                                          "…")}))
                                (dispatch {:event/type :system/message
                                           :text (str "Running agent not found: "
                                                      (or id "<missing>"))})))

                            (= arg "diff")
                            (let [id (second args)
                                  agent (some #(when (= id (:id %)) %) agents)]
                              (if-let [worktree (:worktree agent)]
                                (runtime/agent-diff!
                                 {:worktree worktree
                                  :on-done!
                                  (fn [{:keys [ok? out error]}]
                                    (dispatch
                                     {:event/type (if ok?
                                                    :system/message :turn/failed)
                                      :text (when ok?
                                              (if (str/blank? out)
                                                "Agent has no changes."
                                                (subs out 0
                                                      (min 12000
                                                           (count out)))))
                                      :message (when-not ok? error)}))})
                                (dispatch {:event/type :system/message
                                           :text (str "Writable agent not found: "
                                                      (or id "<missing>"))})))

                            (= arg "apply")
                            (let [id (second args)
                                  agent (some #(when (= id (:id %)) %) agents)]
                              (if-let [worktree (:worktree agent)]
                                (runtime/apply-agent-diff!
                                 {:root (runtime/project-root)
                                  :worktree worktree
                                  :on-done!
                                  (fn [{:keys [ok? error]}]
                                    (when ok?
                                      (update-agent! id #(assoc % :applied? true)))
                                    (dispatch
                                     (if ok?
                                       {:event/type :system/message
                                        :text (str "Applied agent " id
                                                   " patch to the parent workspace.")}
                                       {:event/type :turn/failed
                                        :message error})))})
                                (dispatch {:event/type :system/message
                                           :text (str "Writable agent not found: "
                                                      (or id "<missing>"))})))

                            (= arg "cleanup")
                            (let [id (second args)
                                  agent (some #(when (= id (:id %)) %) agents)]
                              (if (and (:worktree agent)
                                       (not= :running (:status agent)))
                                (runtime/remove-worktree!
                                 {:root (runtime/project-root)
                                  :worktree (:worktree agent)
                                  :on-done!
                                  (fn [{:keys [ok? error]}]
                                    (when ok?
                                      (update-agent! id
                                                     #(dissoc % :worktree)))
                                    (dispatch
                                     (if ok?
                                       {:event/type :system/message
                                        :text (str "Removed worktree for " id ".")}
                                       {:event/type :turn/failed
                                        :message error})))})
                                (dispatch {:event/type :system/message
                                           :text (str "Completed writable agent not found: "
                                                      (or id "<missing>"))})))

                            :else
                            (if-let [agent (some #(when (= arg (:id %)) %) agents)]
                              (dispatch
                               {:event/type :system/message
                                :text (str (:id agent) "  "
                                           (name (:status agent)) "\n"
                                           "model: " (:model agent) "\n"
                                           "mode: " (name (:mode agent)) "\n"
                                           "task: " (:task agent)
                                           (when-let [worktree (:worktree agent)]
                                             (str "\nworktree: " worktree))
                                           (when (:applied? agent)
                                             "\napplied: yes")
                                           (when-let [tool (:current-tool agent)]
                                             (str "\ncurrent tool: " tool))
                                           (when-let [result (:result agent)]
                                             (str "\n\n" result))
                                           (when-let [error (:error agent)]
                                             (str "\n\nerror: " error)))})
                              (dispatch {:event/type :system/message
                                         :text (str "Agent not found: " arg)})))
                          command
                          (dispatch {:event/type :system/message
                                     :text (str "Unknown command: " command
                                                ". Type /help.")})
                          :else
                          (do
                            (dispatch {:event/type :turn/submitted :text text})
                            (set! (.-current child-ref)
                                  (runtime/start-turn!
                                   {:app-dir (runtime/app-dir)
                                    :root (runtime/project-root)
                                    :model selected-model :text text
                                    :emit! dispatch :on-exit! done!}))))
                        (set-input "")))))]
    (useInput
     (fn [pressed key]
       (when (and working? (.-ctrl key) (= "c" pressed))
         (runtime/kill! (.-current child-ref))
         (dispatch {:event/type :turn/cancelled})
         (done!)))
     #js {:isActive working?})
    (el Box {:flexDirection "column" :paddingLeft 1 :paddingRight 1}
        (el Box {:flexDirection "column" :marginBottom 1}
            (el Text {:bold true} (el Text {:color "cyan"} "kotoba") " code")
            (el Text {:dimColor true}
                (str (runtime/project-root) "  ·  " selected-model)))
        (into-array
         (map-indexed
          (fn [i message]
            (react/createElement message-view
                                 #js {:key i :role (:role message)
                                      :text (:text message)}))
          (:messages ui-state)))
        (into-array
         (map-indexed
          (fn [i tool]
            (react/createElement tool-view
                                 (js/Object.assign #js {:key i} (clj->js tool))))
          (:tools ui-state)))
        (when-let [error (:error ui-state)]
          (el Box {:marginBottom 1}
              (el Text {:color "red"}
                  (str "✕ " error
                       (when-not (str/includes? error "/resume")
                         "  Type /resume to continue.")))))
        (if working?
          (el Text {:color "yellow"} "✦ Working…  Ctrl-C to cancel")
          (el Box {:flexDirection "column"}
              (when-let [items (seq (commands/suggestions input))]
                (el Box {:flexDirection "column" :marginLeft 2 :marginBottom 1}
                    (into-array
                     (map-indexed
                      (fn [i item]
                        (el Text {:key i :dimColor true}
                            (str (:usage item) "  " (:description item))))
                      items))))
              (el Box {:borderStyle "round" :borderColor "gray" :paddingLeft 1}
                  (el Text {:color "cyan"} "❯ ")
                  (react/createElement
                   composer-input
                   #js {:value input :onChange set-input :onSubmit submit!
                        :maxColumns (max 12 (- (or (.-columns stdout) 80) 8))
                        :placeholder "Ask about the codebase or type /help…"})))))))

(defn -main []
  (render (react/createElement app))
  nil)
