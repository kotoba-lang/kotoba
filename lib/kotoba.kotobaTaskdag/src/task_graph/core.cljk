(ns task-graph.core
  "Pure state+event -> next-state projector for EDN task-dependency graphs
  (a topology base-catalog + an append-only progress ledger). No I/O:
  callers supply already-loaded catalog/ledger data (e.g. read from
  90-docs/task-graphs/*.datoms.edn + task-graph-ledger.edn in
  com-junkawasaki/root) and get back computed status/readiness.

  This is a `kotoba/pure` decision function (ADR-2607201300 in
  com-junkawasaki/root): (catalog, ledger) in, a ready-set out, nothing
  else. Dispatching a ready task, gating it through a Governor/HITL check,
  and appending the resulting progress event are all the caller's job, not
  this namespace's — see ADR-2607202800 for the EDN schema and the
  local-manimani-cdci Phase 3 integration this was built for.")

(defn latest-status
  "Last (highest :event/seq) :event/type recorded for task-id in ledger, or
   nil if the task has no events yet (== :pending)."
  [ledger task-id]
  (->> ledger
       (filter #(= task-id (:task/id %)))
       (sort-by :event/seq)
       last
       :event/type))

(defn task-status
  "One of :pending | :dispatched | :started | :completed | :blocked | :skipped."
  [ledger task-id]
  (or (latest-status ledger task-id) :pending))

(def terminal-statuses
  "Statuses ready-tasks will never re-surface a task from."
  #{:completed :blocked :skipped})

(defn ready-tasks
  "catalog: seq of task maps ({:task/id :task/requires ...}; workflow maps,
   which have no :task/id, are ignored). ledger: seq of {:task/id
   :event/type :event/seq ...} event maps.

   Returns the catalog entries (each with :task/status assoc'd as :ready)
   that are not yet terminal and whose every :task/requires entry IS
   :completed."
  [catalog ledger]
  (let [tasks (filter :task/id catalog)
        completed? (fn [id] (= :completed (task-status ledger id)))]
    (->> tasks
         (remove (fn [t] (contains? terminal-statuses (task-status ledger (:task/id t)))))
         (filter (fn [t] (every? completed? (:task/requires t))))
         (map (fn [t] (assoc t :task/status :ready))))))

(defn all-statuses
  "Every task in catalog, each with its current :task/status assoc'd."
  [catalog ledger]
  (->> (filter :task/id catalog)
       (map (fn [t] (assoc t :task/status (task-status ledger (:task/id t)))))))

(defn workflow-done?
  "True when every task belonging to workflow-id is :completed or :skipped.
   A :blocked task means the workflow is stuck, not done, so this returns
   false (not true) in that case — callers that want to distinguish
   \"done\" from \"stuck\" should inspect all-statuses directly."
  [catalog ledger workflow-id]
  (let [tasks (filter #(= workflow-id (:task/workflow %)) (filter :task/id catalog))]
    (and (seq tasks)
         (every? #(#{:completed :skipped} (task-status ledger (:task/id %))) tasks))))
