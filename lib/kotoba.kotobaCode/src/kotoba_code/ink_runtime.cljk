(ns kotoba-code.ink-runtime
  "Leftover nbb Ink host-listen HOLD — not operator start.
  :run is gone. Do not wrap Datalevin/LMDB JNI as a C .so."
  (:require [kotoba.lang.text :as str]
            ["node:child_process" :refer [spawn]]
            ["node:fs" :as fs]
            ["node:os" :as os]
            ["node:path" :as path]))

(def tool-start-re #"^\[tool:start\]\s+([^\s]+)")
(def tool-end-re #"^\[tool:end\]\s+([^\s]+)\s+.*?(?:->\s*(.*))?$")

(defn parse-output!
  "Consume complete JVM output lines and emit structured Ink UI events."
  [parser text emit!]
  (let [combined (str (:tail @parser) text)
        parts (str/split combined #"\r?\n" -1)
        complete (butlast parts)]
    (swap! parser assoc :tail (last parts))
    (doseq [line complete]
      (cond
        (= line "-- agent --")
        (swap! parser assoc :mode :assistant)

        (str/starts-with? line "-- gate --")
        (swap! parser assoc :mode nil)

        (str/starts-with? line "-- error --")
        (let [message (str/trim (subs line (count "-- error --")))]
          (swap! parser assoc :failed? true :mode nil :error message)
          (emit! {:event/type :turn/failed :message message}))

        (str/starts-with? line "-- supervisor -- refusing task:")
        (let [message (-> line
                          (subs (count "-- supervisor -- "))
                          (str/replace ":resume" "/resume")
                          str/trim)]
          (swap! parser assoc :failed? true :mode nil :error message)
          (emit! {:event/type :turn/failed :message message}))

        (str/starts-with? line "[model:fallback]")
        (emit! {:event/type :model/fallback
                :model (second (str/split line #"\s+"))})

        (re-find tool-start-re line)
        (let [[_ name] (re-find tool-start-re line)
              id (str name "-" (random-uuid))]
          (swap! parser assoc-in [:tool-ids name] id)
          (emit! {:event/type :tool/started :id id :name name}))

        (re-find tool-end-re line)
        (let [[_ name summary] (re-find tool-end-re line)
              id (get-in @parser [:tool-ids name])]
          (emit! {:event/type :tool/completed
                  :id id :name name :summary (or summary "")}))

        (= :assistant (:mode @parser))
        (swap! parser update :answer conj line)

        (not (str/blank? line))
        (swap! parser update :diagnostics conj line)

        :else nil))))

(defn start-turn!
  [{:keys [app-dir root model text emit! on-exit!]}]
  ;; Leftover nbb host-listen (not operator start). :run is gone.
  (let [args (cond-> ["-M" "-m" "kotoba-code.main" text root] model (conj model))
        child (spawn "clojure" (clj->js args)
                     #js {:cwd app-dir
                          :env (js/Object.assign
                                #js {}
                                js/process.env
                                #js {:KC_TOOL_TRANSCRIPT "false"})})
        parser (atom {:tail "" :mode nil :answer [] :tool-ids {}
                      :stderr [] :diagnostics [] :failed? false})]
    (.setEncoding (.-stdout child) "utf8")
    (.setEncoding (.-stderr child) "utf8")
    (.on (.-stdout child) "data" #(parse-output! parser % emit!))
    (.on (.-stderr child) "data"
         #(when-not (str/blank? %)
            (swap! parser update :stderr conj %)))
    (.on child "error"
         #(emit! {:event/type :turn/failed :message (.-message %)}))
    (.on child "close"
         (fn [code _signal]
           ;; Node may deliver a final stdout chunk without a newline.
           (when (seq (:tail @parser))
             (parse-output! parser "\n" emit!))
           (let [answer (->> (:answer @parser)
                             (str/join "\n")
                             str/trim)
                 stderr (->> (:stderr @parser)
                             (str/join "")
                             str/trim)
                 diagnostics (->> (:diagnostics @parser)
                                  (take-last 3)
                                  (str/join " · ")
                                  str/trim)]
             (when (and (not (:failed? @parser)) (seq answer))
               (emit! {:event/type :assistant/completed :text answer}))
             (when (and (not (:failed? @parser)) (str/blank? answer) (not= 0 code))
               (emit! {:event/type :turn/failed
                       :message (if (seq stderr)
                                  stderr
                                  (if (seq diagnostics)
                                    diagnostics
                                    (str "Agent exited with status " code)))}))
             (on-exit!))))
    child))

(defn start-control!
  [{:keys [app-dir root action emit! on-exit!]}]
  (let [child (spawn "clojure" #js ["-M" "-m" "kotoba-code.main" action root]
                     #js {:cwd app-dir :env js/process.env})]
    (.on child "close"
         (fn [code _]
           (if (zero? code)
             (emit! {:event/type :session/resumed})
             (emit! {:event/type :turn/failed
                     :message (str action " failed with status " code)}))
           (on-exit!)))
    child))

(defn start-command!
  "Run a read-only JVM CLI command and return its rendered output to the UI."
  [{:keys [app-dir args emit! on-exit!]}]
  (let [child (spawn "clojure" (clj->js (into ["-M" "-m" "kotoba-code.main"] args))
                     #js {:cwd app-dir :env js/process.env})
        stdout (atom [])
        stderr (atom [])]
    (.setEncoding (.-stdout child) "utf8")
    (.setEncoding (.-stderr child) "utf8")
    (.on (.-stdout child) "data" #(swap! stdout conj %))
    (.on (.-stderr child) "data" #(swap! stderr conj %))
    (.on child "error"
         #(emit! {:event/type :turn/failed :message (.-message %)}))
    (.on child "close"
         (fn [code _]
           (let [out (str/trim (str/join "" @stdout))
                 err (str/trim (str/join "" @stderr))]
             (if (zero? code)
               (emit! {:event/type :system/message
                       :text (if (seq out) out "Command completed.")})
               (emit! {:event/type :turn/failed
                       :message (if (seq err) err
                                  (if (seq out) out
                                      (str "Command exited with status " code)))}))
             (on-exit!))))
    child))

(defn start-subtask!
  [{:keys [app-dir root model id text read-only? on-event! on-done!]
    :or {read-only? true}}]
  (let [task (str text
                  "\n\n[SUBTASK MODE] Work independently. "
                  (if read-only?
                    "Do not modify files. Return a concise finding for the parent agent."
                    (str "You are in an isolated git worktree. Make only the requested "
                         "changes and leave them uncommitted for parent review.")))
        args (cond-> ["-M" "-m" "kotoba-code.main" task root] model (conj model))
        child (spawn "clojure" (clj->js args)
                     #js {:cwd app-dir
                          :env (js/Object.assign
                                #js {} js/process.env
                                #js {:KC_LOOP_ID (str "kotoba-subtask-" id)
                                     :KC_SESSION (str "kotoba-subtask-" id)
                                     :KC_SUBTASK_READ_ONLY (str read-only?)
                                     :KC_TOOL_TRANSCRIPT "false"})})
        parser (atom {:tail "" :mode nil :answer [] :tool-ids {}
                      :stderr [] :diagnostics [] :failed? false})]
    (.setEncoding (.-stdout child) "utf8")
    (.setEncoding (.-stderr child) "utf8")
    (.on (.-stdout child) "data" #(parse-output! parser % on-event!))
    (.on (.-stderr child) "data" #(swap! parser update :stderr conj %))
    (.on child "error"
         #(on-done! {:status :failed :error (.-message %)}))
    (.on child "close"
         (fn [code signal]
           (when (seq (:tail @parser))
             (parse-output! parser "\n" on-event!))
           (let [answer (->> (:answer @parser) (str/join "\n") str/trim)
                 stderr (->> (:stderr @parser) (str/join "") str/trim)]
             (on-done! (if (and (zero? code) (seq answer))
                         {:status :completed :result answer}
                         {:status (if (or signal (= code 130))
                                   :cancelled :failed)
                          :error (or (:error @parser)
                                     (when (seq stderr) stderr)
                                     (str "Subtask exited with status " code))})))))
    child))

(defn- collect-process!
  [command args {:keys [cwd stdin on-done!]}]
  (let [child (spawn command (clj->js args) #js {:cwd cwd :env js/process.env})
        stdout (atom [])
        stderr (atom [])]
    (.setEncoding (.-stdout child) "utf8")
    (.setEncoding (.-stderr child) "utf8")
    (.on (.-stdout child) "data" #(swap! stdout conj %))
    (.on (.-stderr child) "data" #(swap! stderr conj %))
    (when stdin
      (.end (.-stdin child) stdin))
    (.on child "error"
         #(on-done! {:ok? false :error (.-message %)}))
    (.on child "close"
         (fn [code _]
           (on-done! {:ok? (zero? code)
                      :code code
                      :out (str/join "" @stdout)
                      :error (str/trim (str/join "" @stderr))})))
    child))

(defn worktree-path [root id]
  (let [base (.join path (.tmpdir os) "kotoba-code-worktrees")]
    (.mkdirSync fs base #js {:recursive true})
    (.join path base (str (.basename path root) "-" id))))

(defn create-worktree!
  [{:keys [root id on-done!]}]
  (let [target (worktree-path root id)]
    (collect-process!
     "git" ["worktree" "add" "--detach" target "HEAD"]
     {:cwd root
      :on-done! #(on-done! (assoc % :path target))})))

(defn agent-diff!
  [{:keys [worktree on-done!]}]
  (collect-process!
   "git" ["add" "-N" "."]
   {:cwd worktree
    :on-done!
    (fn [prepared]
      (if-not (:ok? prepared)
        (on-done! prepared)
        (collect-process! "git" ["diff" "--binary" "HEAD"]
                          {:cwd worktree :on-done! on-done!})))}))

(defn apply-agent-diff!
  [{:keys [root worktree on-done!]}]
  (agent-diff!
   {:worktree worktree
    :on-done!
    (fn [{:keys [ok? out] :as diff-result}]
      (if-not ok?
        (on-done! diff-result)
        (if (str/blank? out)
          (on-done! {:ok? false :error "Agent has no changes."})
          (collect-process!
           "git" ["apply" "--check" "-"]
           {:cwd root
            :stdin out
            :on-done!
            (fn [checked]
              (if-not (:ok? checked)
                (on-done!
                 (assoc checked :error
                        (str "Patch conflicts with parent workspace: "
                             (:error checked))))
                (collect-process!
                 "git" ["apply" "-"]
                 {:cwd root :stdin out :on-done! on-done!})))}))))}))

(defn remove-worktree!
  [{:keys [root worktree on-done!]}]
  (let [managed-root (.join path (.tmpdir os) "kotoba-code-worktrees")
        managed? (= managed-root (.dirname path worktree))]
    (collect-process!
     "git" ["worktree" "remove" "--force" worktree]
     {:cwd root
      :on-done!
      (fn [result]
        (if (or (:ok? result) (not managed?))
          (on-done! result)
          (try
            (.rmSync fs worktree #js {:recursive true :force true})
            (collect-process! "git" ["worktree" "prune"]
                              {:cwd root :on-done! on-done!})
            (catch :default e
              (on-done! {:ok? false :error (.-message e)})))))})))

(defn kill! [child]
  (when child (.kill child "SIGINT")))

(defn app-dir []
  (or (.-KOTOBA_CODE_HOME js/process.env)
      (js/process.cwd)))

(defn project-root []
  (or (.-KOTOBA_PROJECT_ROOT js/process.env)
      (js/process.cwd)))

(defn model-id []
  (or (.-KOTOBA_MODEL js/process.env)
      "z-ai/glm-5.2"))
