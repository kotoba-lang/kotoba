(ns browseragent.memory
  "Datom read/write helpers over the `langchain.db` Datomic-compatible
  store. All writes go through an injected `:db-api` map (default
  `langchain.db/api`) so a real Datomic Local / DataScript backend can
  be swapped in unchanged.

  Everything the agent learns or produces lands here as datoms, which
  makes the run a queryable, time-travelable audit trail — the main
  thing a black-box super-agent cannot give you."
  (:require [langchain.db :as db]))

(def default-api db/api)

(defn ensure-task!
  "Idempotently upserts the task entity. Returns task-id."
  [conn db-api task-id prompt]
  ((:transact! db-api) conn [{:task/id task-id :task/prompt prompt :task/status :running}])
  task-id)

(defn set-task-status! [conn db-api task-id status]
  ((:transact! db-api) conn [{:task/id task-id :task/status status}]))

(defn record-fact!
  "Persist a semantic-memory fact with optional source URL."
  [conn db-api task-id {:keys [kind key value source-url] :or {kind :fact}}]
  ((:transact! db-api) conn
   [{:mem/task [:task/id task-id]
     :mem/kind kind
     :mem/key (str key)
     :mem/value (str value)
     :mem/source-url (str source-url)}]))

(defn record-artifact!
  "Persist a generated artifact (slides/sheet/doc/page/file body)."
  [conn db-api task-id {:keys [kind title body mime] :or {kind :doc mime "text/markdown"}}]
  ((:transact! db-api) conn
   [{:artifact/task [:task/id task-id]
     :artifact/kind kind
     :artifact/title (str title)
     :artifact/body (str body)
     :artifact/mime mime}]))

(defn record-delegation!
  "Persist one MoA routing decision and its outcome."
  [conn db-api task-id {:keys [step agent model goal result]}]
  ((:transact! db-api) conn
   [{:deleg/task [:task/id task-id]
     :deleg/step step
     :deleg/agent agent
     :deleg/model (str model)
     :deleg/goal (str goal)
     :deleg/result (str result)}]))

;; ── queries (return plain data; handy in tests and the UI audit tab) ──

(defn facts-for [conn db-api task-id]
  ((:q db-api)
   '[:find ?k ?v ?src
     :in $ ?tid
     :where
     [?t :task/id ?tid]
     [?m :mem/task ?t]
     [?m :mem/key ?k] [?m :mem/value ?v] [?m :mem/source-url ?src]]
   ((:db db-api) conn) task-id))

(defn artifacts-for [conn db-api task-id]
  ((:q db-api)
   '[:find ?kind ?title ?body
     :in $ ?tid
     :where
     [?t :task/id ?tid]
     [?a :artifact/task ?t]
     [?a :artifact/kind ?kind] [?a :artifact/title ?title] [?a :artifact/body ?body]]
   ((:db db-api) conn) task-id))

(defn delegations-for [conn db-api task-id]
  (sort-by
   first
   ((:q db-api)
    '[:find ?step ?agent ?goal
      :in $ ?tid
      :where
      [?t :task/id ?tid]
      [?d :deleg/task ?t]
      [?d :deleg/step ?step] [?d :deleg/agent ?agent] [?d :deleg/goal ?goal]]
    ((:db db-api) conn) task-id)))

(defn urls-visited
  "Every URL the agent's actions touched — straight off the
  browser-use action log."
  [conn db-api]
  (distinct
   (map first
        ((:q db-api)
         '[:find ?url :where [?a :action/url ?url]]
         ((:db db-api) conn)))))
