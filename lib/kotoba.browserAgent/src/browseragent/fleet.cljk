(ns browseragent.fleet
  "The sub-agent fleet the supervisor delegates to.

  A sub-agent is a map {:kind kw :description str :run (fn [m] → result-map)}
  where m = {:goal str :ctx ctx} and the result-map is at least
  {:result str}. Adding an agent is adding a map — same extensibility
  as browser-use-clj's action registry.

    :web      browser-use-clj over the agent's *owned* browser
    :research langgraph ReAct with injected search/fetch host fns
    :coder    langgraph ReAct with an injected code-exec host fn
    :author   langgraph ReAct whose render tool emits an artifact

  All non-web agents share one ReAct shape; the model and the host
  capabilities (search-fn / fetch-fn / exec-fn / render-fn) are
  injected through ctx, keeping this namespace WASM-pure."
  (:require [browseruse.agent :as bua]
            [browseragent.memory :as mem]
            [langgraph.prebuilt :as prebuilt]
            [langgraph.graph :as g]
            [langchain.message :as msg]
            [langchain.model :as model]))

(defn- model-for [ctx kind]
  (or (get-in ctx [:models kind])
      (:model ctx)
      (throw (ex-info (str "No model for sub-agent " kind) {:kind kind}))))

(defn- react-run
  "Run a one-shot ReAct sub-agent and return its final text."
  [{:keys [goal model tools system]}]
  (let [agent (prebuilt/create-react-agent {:model model :tools tools :system system})
        out (g/invoke agent {:messages [(msg/user goal)]})]
    (msg/text (msg/last-message (:messages out)))))

;; ───────────────────────── web ─────────────────────────

(def web-agent
  {:kind :web
   :description "Browse the web with the agent's own browser to gather info or act."
   :run (fn [{:keys [goal ctx]}]
          (let [out (bua/run {:model (model-for ctx :web)
                              :browser (:browser ctx)
                              :task goal
                              :history-conn (:conn ctx)
                              :db-api (:db-api ctx)
                              :session-id (:session-id ctx)
                              :max-steps (or (:max-steps ctx) 25)})]
            {:result (or (:result out) "")
             :done (:done out)
             :steps (:steps out)}))})

;; ──────────────────── research / coder / author ────────────────────

(defn- research-tools [ctx]
  (let [{:keys [search-fn fetch-fn conn db-api task-id]} ctx]
    [{:name "web_search" :description "Search the web; returns result snippets."
      :schema {:type "object" :properties {:query {:type "string"}} :required ["query"]}
      :fn (fn [{:keys [query]}] (str ((or search-fn (constantly "(no search-fn)")) query)))}
     {:name "fetch_url" :description "Fetch a URL; records it as a source."
      :schema {:type "object" :properties {:url {:type "string"}} :required ["url"]}
      :fn (fn [{:keys [url]}]
            (let [body (str ((or fetch-fn (constantly "(no fetch-fn)")) url))]
              (when conn
                (mem/record-fact! conn db-api task-id
                                  {:kind :source :key url :value (subs body 0 (min 80 (count body)))
                                   :source-url url}))
              body))}]))

(def research-agent
  {:kind :research
   :description "Deep-research a question across sources and synthesize a cited answer."
   :run (fn [{:keys [goal ctx]}]
          (let [r (react-run {:goal goal :model (model-for ctx :research)
                              :tools (research-tools ctx)
                              :system "You are a research agent. Use web_search and fetch_url, then give a concise, sourced answer."})]
            (when (:conn ctx)
              (mem/record-fact! (:conn ctx) (:db-api ctx) (:task-id ctx)
                                {:kind :fact :key "research" :value r}))
            {:result r}))})

(defn- coder-tools [ctx]
  (let [{:keys [exec-fn]} ctx]
    [{:name "run_code" :description "Execute code in the sandbox; returns stdout/value."
      :schema {:type "object" :properties {:code {:type "string"}} :required ["code"]}
      :fn (fn [{:keys [code]}] (str ((or exec-fn (constantly "(no exec-fn)")) code)))}]))

(def coder-agent
  {:kind :coder
   :description "Write and run code to compute or verify a result."
   :run (fn [{:keys [goal ctx]}]
          {:result (react-run {:goal goal :model (model-for ctx :coder)
                               :tools (coder-tools ctx)
                               :system "You are a coding agent. Write code, run it with run_code, return the result."})})})

(defn- author-tools [ctx]
  (let [{:keys [render-fn conn db-api task-id]} ctx]
    [{:name "render_artifact"
      :description "Produce a deliverable artifact (slides/sheet/doc/page)."
      :schema {:type "object"
               :properties {:kind {:type "string"} :title {:type "string"} :body {:type "string"}}
               :required ["kind" "title" "body"]}
      :fn (fn [{:keys [kind title body]}]
            (let [rendered (str ((or render-fn (fn [m] (:body m)))
                                 {:kind kind :title title :body body}))]
              (when conn
                (mem/record-artifact! conn db-api task-id
                                      {:kind (keyword kind) :title title :body rendered}))
              (str "Artifact saved: " title)))}]))

(def author-agent
  {:kind :author
   :description "Generate a deliverable (slides/sheet/doc/page) as an artifact."
   :run (fn [{:keys [goal ctx]}]
          {:result (react-run {:goal goal :model (model-for ctx :author)
                               :tools (author-tools ctx)
                               :system "You are an authoring agent. Call render_artifact exactly once to produce the deliverable."})})})

(def default-fleet [web-agent research-agent coder-agent author-agent])

(defn by-kind [fleet kind]
  (some #(when (= kind (:kind %)) %) fleet))

(defn dispatch
  "Route one plan step to its assigned sub-agent."
  [fleet {:keys [assignee goal]} ctx]
  (if-let [a (by-kind fleet assignee)]
    ((:run a) {:goal goal :ctx ctx})
    {:result (str "No sub-agent for " assignee) :error true}))
