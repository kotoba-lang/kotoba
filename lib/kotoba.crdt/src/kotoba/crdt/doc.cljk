(ns kotoba.crdt.doc
  "Entity-attribute document CRDT: an OR-Set of entity ids (kotoba.crdt.orset)
  plus, per entity, a map of field -> LWW-Register (kotoba.crdt.register).
  This is the shape a Kotoba document actually needs: entities are slides,
  shapes, blocks, rows... — things editors concurrently add/remove — and
  fields are their scalar attributes (:slides/x, :slides/color, :slides/text,
  ...). Two editors adding different shapes, or editing different fields of
  the same shape, always converge with both edits intact; two editors editing
  the *same* field of the *same* entity converge deterministically to one
  winner (kotoba.crdt.register's documented LWW limit).

  Two ways to synchronize replicas, both supported:
  - op-based: apply-op each op as it's produced/received (pair with a
    kotobase-style append-only log — ops ARE the log entries, replay from
    :seq via `read(since)` for a late-joining or reconnecting editor).
  - state-based: merge-docs two full document snapshots directly (for
    reconciling a replica that's been offline with no op history)."
  (:require [kotoba.crdt.clock :as clock]
            [kotoba.crdt.orset :as orset]
            [kotoba.crdt.register :as register]))

(defn init [] {:crdt/entities (orset/init) :crdt/fields {}})

(defn apply-op
  "Applies one op to `doc`. Idempotent and order-independent: replaying the
  same op twice, or two ops in either order, always converges."
  [doc op]
  (case (:crdt/op op)
    :add (update doc :crdt/entities orset/add (:crdt/entity op) (:crdt/tag op))
    :remove (update doc :crdt/entities orset/remove-tags (:crdt/tags op))
    :set-field (update-in doc [:crdt/fields (:crdt/entity op) (:crdt/field op)]
                          register/merge-register
                          (register/write (:crdt/value op) (:crdt/stamp op)))
    doc))

(defn apply-ops [doc ops] (reduce apply-op doc ops))

(defn- next-stamp [clock]
  (let [clock' (clock/tick clock)]
    [clock' (clock/stamp clock')]))

(defn add-entity
  "Returns [doc' clock' op]. Broadcast `op` to other replicas (e.g. append it
  to the shared kotobase log); they converge by calling `apply-op` with it."
  [doc clock entity-id]
  (let [[clock' stamp] (next-stamp clock)
        tag [(:crdt/actor stamp) (:crdt/counter stamp)]
        op {:crdt/op :add :crdt/entity entity-id :crdt/tag tag :crdt/stamp stamp}]
    [(apply-op doc op) clock' op]))

(defn remove-entity
  "Tombstones only the add-tags this replica has itself observed for
  entity-id — an add concurrent with this remove (not yet observed here)
  survives on whichever replica produced it, per OR-Set semantics."
  [doc clock entity-id]
  (let [[clock' stamp] (next-stamp clock)
        tags (orset/observed-tags (:crdt/entities doc) entity-id)
        op {:crdt/op :remove :crdt/entity entity-id :crdt/tags tags :crdt/stamp stamp}]
    [(apply-op doc op) clock' op]))

(defn set-field [doc clock entity-id field value]
  (let [[clock' stamp] (next-stamp clock)
        op {:crdt/op :set-field :crdt/entity entity-id :crdt/field field
            :crdt/value value :crdt/stamp stamp}]
    [(apply-op doc op) clock' op]))

(defn receive
  "Apply a remote op and advance the local clock past it (Lamport receive)."
  [doc clock op]
  [(apply-op doc op) (clock/observe clock (:crdt/stamp op))])

(defn entities [doc] (orset/elements (:crdt/entities doc)))

(defn get-field [doc entity-id field]
  (register/value (get-in doc [:crdt/fields entity-id field])))

(defn entity-snapshot [doc entity-id]
  (into {}
        (map (fn [[field register]] [field (register/value register)]))
        (get (:crdt/fields doc) entity-id)))

(defn snapshot
  "The visible document as plain EDN: {entity-id {field value ...} ...}.
  Tombstoned entities are omitted; their field registers are retained
  internally (not garbage collected) so a concurrent add can still resurrect
  the same entity id correctly."
  [doc]
  (into {} (map (fn [id] [id (entity-snapshot doc id)])) (entities doc)))

(defn merge-docs
  "State-based merge of two full document snapshots — commutative,
  associative, idempotent, same as op replay but without needing history."
  [a b]
  {:crdt/entities (orset/merge-orset (:crdt/entities a) (:crdt/entities b))
   :crdt/fields (merge-with (fn [fa fb] (merge-with register/merge-register fa fb))
                            (:crdt/fields a) (:crdt/fields b))})
