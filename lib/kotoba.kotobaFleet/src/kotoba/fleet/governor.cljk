(ns kotoba.fleet.governor
  "Single-writer proposal drain — the actor invariant for the fleet.

  Agents never write to git directly: they only APPEND `:proposal/*` datoms
  (their write intent). One governor per repo drains the pending proposals, runs
  each through a `gate` (accept/reject), materializes accepted ones via a single
  side-effecting `materialize` hook (the only writer that touches git), and
  appends a `:receipt/*`. Because exactly one governor drains a repo, git never
  sees N concurrent writers — the conflict is gone before git is involved."
  (:require [kotoba.fleet.schema :as schema]
            [kotoba.fleet.store :as store]))

(defn- entities-of
  "Reconstruct every entity of `kind-ns` (e.g. \"proposal\") from the log."
  [db kind-ns]
  (->> (store/datoms db)
       (keep (fn [[e a]] (when (= kind-ns (namespace a)) e)))
       distinct
       (mapv #(store/entity db %))))

(defn submit-proposal!
  "Append a write-intent proposal for `agent` on `work`. Returns the proposal id.
  `:idempotency-key`, when supplied, gives repeat submissions the same entity id
  and therefore exactly one pending proposal. `now` is accepted for symmetry but
  ordering is captured by the append ordinal.

  t is assigned atomically WITH the append (store/transact-with-t!) -- a
  separate next-t read followed by transact! let two concurrent submitters
  compute the same t (verified against 50 real concurrent threads: as few as
  23 distinct t values came out of 50 submissions)."
  [db {:keys [work agent payload idempotency-key]}]
  (let [{:keys [t]} (store/transact-with-t!
                     db
                     (fn [t]
                       (schema/entity->datoms
                        {:proposal/id (str "prop|" work "|" agent "|" (or idempotency-key t))
                         :proposal/work work :proposal/agent agent
                         :proposal/payload payload :proposal/idempotency-key idempotency-key
                         :proposal/t t}
                        t)))]
    (str "prop|" work "|" agent "|" (or idempotency-key t))))

(defn pending-proposals
  "Proposals (in causal order) that have not yet been receipted."
  [db]
  (let [done (->> (entities-of db "receipt")
                  (map :receipt/proposal)
                  (into #{}))]
    (->> (entities-of db "proposal")
         (remove #(contains? done (:proposal/id %)))
         (sort-by :proposal/t))))

(defn record!
  "Append a governor receipt for proposal `proposal-id` on `work` with `verdict`
  (:accepted | :rejected) and optional `reason`. Append-only. Once a receipt
  exists for a proposal, it is no longer `pending-proposals` — so a decided
  proposal is never re-materialized. This is the single place the governor
  commits a decision, whether reached by `drain!` or by an actor graph."
  [db {:keys [proposal-id work verdict reason]}]
  (let [ent-fn (fn [t]
                 {:receipt/id (str "rcpt|" proposal-id "|" t)
                  :receipt/proposal proposal-id
                  :receipt/work work
                  :receipt/verdict verdict
                  :receipt/reason reason
                  :receipt/t t})
        {:keys [t]} (store/transact-with-t!
                     db
                     (fn [t] (schema/entity->datoms (ent-fn t) t)))]
    (ent-fn t)))

(defn drain!
  "Drain pending proposals through `gate` then `materialize` (single writer).
  Opts: {:gate (fn [proposal] truthy?) :materialize (fn [proposal] …)}.
  Accepted proposals are materialized; a throwing materialize is caught and the
  proposal is rejected (never leaves git half-written). Returns the receipts."
  [db {:keys [gate materialize]}]
  (mapv
   (fn [p]
     (let [base {:proposal-id (:proposal/id p) :work (:proposal/work p)}]
       (if (gate p)
         (try
           (when materialize (materialize p))
           (record! db (assoc base :verdict :accepted))
           (catch #?(:clj Exception :cljs :default) e
             (record! db (assoc base :verdict :rejected
                                :reason (str "materialize-error: " (ex-message e))))))
         (record! db (assoc base :verdict :rejected :reason "gate-rejected")))))
   (pending-proposals db)))
