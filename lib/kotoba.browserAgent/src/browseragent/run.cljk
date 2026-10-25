(ns browseragent.run
  "Top-level entry: the one place host capabilities are injected.

  `run` wires a task through planner → MoA supervisor → fleet, with
  the agent's *owned* browser, and persists everything as datoms.
  Nothing here does I/O on its own — models, the browser provider, the
  store, and the search/fetch/exec/render/emit functions are all
  passed in, so the same call runs on the JVM, a WASM host, or in the
  cljs UI.

    (run {:task \"…\"
          :models {:web m :research m :coder m :author m}
          :browser {:kind :mock :site … :start-url \"…\"}
          :search-fn f :fetch-fn f :exec-fn f :render-fn f
          :plan-fn f          ; or rely on a planner :model
          :conn conn})        ; (make-conn) if omitted"
  (:require [browseragent.schema :as schema]
            [browseragent.planner :as planner]
            [browseragent.supervisor :as sup]
            [browseragent.memory :as mem]
            [browseragent.browser.provider :as provider]
            [langchain.db :as db]))

(defn make-conn
  "A fresh store pre-loaded with the super-agent schema."
  []
  (db/create-conn schema/schema))

(defn run
  [{:keys [task task-id conn db-api models browser start-url browser-id session-id
           plan-fn router aggregator-model replan-fn
           search-fn fetch-fn exec-fn render-fn live max-steps]
    :or {db-api db/api}}]
  (let [conn       (or conn (make-conn))
        task-id    (or task-id "task")
        browser-id (or browser-id (str "browser/" task-id))
        session-id (or session-id task-id)
        start-url  (or start-url (:start-url browser))]
    (mem/ensure-task! conn db-api task-id task)
    (let [owned (when browser
                  (provider/open {:spec browser :conn conn :db-api db-api
                                  :task-id task-id :browser-id browser-id
                                  :start-url start-url :live live}))
          ctx {:models models :model (:research models)
               :browser owned :conn conn :db-api db-api
               :task-id task-id :session-id session-id
               :search-fn search-fn :fetch-fn fetch-fn
               :exec-fn exec-fn :render-fn render-fn
               :live live :max-steps max-steps}
          plan (planner/make-plan task {:plan-fn plan-fn :model (:planner models)})
          _    (planner/persist-plan! conn db-api task-id plan)
          out  (sup/run-supervisor {:ctx ctx :task task :plan plan
                                    :router router
                                    :aggregator-model aggregator-model
                                    :replan-fn replan-fn})]
      (mem/set-task-status! conn db-api task-id :done)
      {:result    (:result out)
       :plan      plan
       :results   (:results out)
       :facts     (mem/facts-for conn db-api task-id)
       :artifacts (mem/artifacts-for conn db-api task-id)
       :delegations (mem/delegations-for conn db-api task-id)
       :urls      (mem/urls-visited conn db-api)
       :conn      conn
       :task-id   task-id})))
