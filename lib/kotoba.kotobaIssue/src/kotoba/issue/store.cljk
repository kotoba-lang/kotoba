(ns kotoba.issue.store
  "The IssueStore contract and a default in-memory implementation.

  Every function in `kotoba.issue.gate`/`kotoba.issue.run` takes a `store`
  satisfying this 4-fn contract instead of assuming any particular database:

    (get-entity  store kind id)      -> entity map or nil
    (put-entity! store kind id m)    -> merges m into the stored entity, returns it
    (list-entities store kind pred)  -> vector of entity maps where (pred m) is truthy
    (append-audit! store audit-map)  -> appends audit-map to an audit log, returns it

  `kind` is a caller-chosen keyword partition (e.g. :issue, :proposal, :review).
  A real deployment backed by Datomic/kotobase can satisfy this same contract
  with a thin adapter over its own transact!/pull/q — the gate/run namespaces
  never assume an in-memory atom.")

(defprotocol IssueStore
  (get-entity [store kind id])
  (put-entity! [store kind id m])
  (list-entities [store kind pred])
  (append-audit! [store audit-map]))

(defrecord MemStore [state]
  IssueStore
  (get-entity [_ kind id]
    (get-in @state [:entities kind id]))
  (put-entity! [_ kind id m]
    (get-in (swap! state update-in [:entities kind id] merge m) [:entities kind id]))
  (list-entities [_ kind pred]
    (let [xs (vals (get-in @state [:entities kind]))]
      (vec (if pred (filter pred xs) xs))))
  (append-audit! [_ audit-map]
    (swap! state update :audit (fnil conj []) audit-map)
    audit-map))

(defn mem-store
  "A fresh in-memory store for standalone use, tests, or a CLI demo. Not
  durable across process restarts -- real deployments supply their own
  IssueStore adapter over a persistent backend."
  []
  (->MemStore (atom {:entities {} :audit []})))

(defn audit-log
  "The full audit trail recorded so far (in insertion order). Only meaningful
  for `mem-store` -- durable backends should query their own audit partition."
  [^MemStore store]
  (get @(:state store) :audit))
