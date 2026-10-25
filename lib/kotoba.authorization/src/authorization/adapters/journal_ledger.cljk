(ns authorization.adapters.journal-ledger
  "The durable `IDecisionLedger`: `langchain.db` holds the index, `journal`
  holds the history, `langchain.persist` is the seam between them.

  This replaces an adapter that rewrote one big EDN map on every write. That
  shape lost the property the datom model is chosen for -- you could read what
  was currently true, never what happened -- and the rebuilt state was never
  queryable, because nothing loaded it back into a database. Here the
  connection replays its own journal on open, so a restarted process answers
  the same Datalog queries the previous one did.

      (require '[authorization.adapters.journal-ledger :as jl])

      (def ledger (jl/journal-decision-ledger {:path \"authz.journal.edn\"}))
      (ledger/persist-decision! ledger request decision {:request-id \"r1\"})
      (jl/decision ledger \"r1\")   ;; the decision, with what was asked"
  (:require [authorization.adapters.decision-ledger :as ledger]
            [authorization.datom :as datom]
            [authorization.schema :as schema]
            [journal.core :as journal]
            [journal.fs :as journal.fs]
            [langchain.db :as db]
            [langchain.persist :as persist]))

(def default-stream
  "The journal stream authorization decisions are written to. Named, so an
  authentication ledger can share one file without either replaying the
  other's events."
  :authz.decisions)

(defn conn
  "A `langchain.db` connection over a journal sink, replayed on open.

  `io` is a `journal.fs` sink (or any `{:read-text :append-text!}` map);
  `stream` defaults to `default-stream`."
  ([io] (conn io default-stream))
  ([io stream]
   (db/create-conn schema/map-schema
                   (persist/scoped (journal/journal io) stream))))

(defn- decision-request-ids
  "The request ids DATOMS issues a decision for."
  [datoms]
  (into [] (keep #(when (contains? % :authz.decision/decision)
                    (:authz.decision/request-id %)))
        datoms))

(defn- already-decided
  "The subset of REQUEST-IDS this database has already issued a decision for.
  A query, not a bookkeeping set kept alongside the data -- the index already
  knows, and a set maintained by hand is a second source of truth that can
  disagree with the first."
  [db request-ids]
  (when (seq request-ids)
    (seq (db/q '[:find [?id ...]
                 :in $ [?id ...]
                 :where
                 [?e :authz.decision/request-id ?id]
                 [?e :authz.decision/decision _]]
               db request-ids))))

(defrecord JournalDecisionLedger [conn]
  ledger/IDecisionLedger
  (transact! [_ datoms opts]
    (when-let [replayed (and (not (:allow-replay? opts))
                             (already-decided (db/db conn) (decision-request-ids datoms)))]
      (throw (ex-info "authorization decision already persisted"
                      {:error :authz.decision/replay
                       :request-ids (vec replayed)})))
    (let [report (db/transact! conn datoms)]
      {:tx/id (or (:tx/id opts) (str "tx-" (:tx report)))
       :tx/datoms (count datoms)
       :tx/request-id (:request-id opts)
       :tx/at (:at opts)})))

(defn journal-decision-ledger
  "A decision ledger durable in an append-only EDN journal.

    {:path \"authz.journal.edn\"}   ;; a file, on the JVM or on Node
    {:io (journal.fs/memory-io)}    ;; any sink, for tests and for hosts
                                    ;; without a filesystem
    {:io io :stream :some.other/stream}"
  [{:keys [path io stream]}]
  (when-not (or path io)
    (throw (ex-info "journal-decision-ledger needs :path or :io" {})))
  (->JournalDecisionLedger (conn (or io (journal.fs/file-io path))
                                 (or stream default-stream))))

;; ── reading the ledger back ──

(def decision-pull
  "Enough of a decision to audit it, with the request it answered nested
  rather than referenced -- the shape the old adapter could only have
  produced by joining two flat vectors by hand."
  [:authz.decision/request-id :authz.decision/decision :authz.decision/by
   :authz.decision/reason :authz.decision/policy-ref :authz.decision/policy-version
   :authz.decision/effect-trace :authz.decision/obligations :authz.decision/issued-at
   {:authz.decision/request [:authz.request/id :authz.request/principal
                             :authz.request/action :authz.request/resource
                             :authz.request/context :authz.request/capability-ref]}])

(defn- decode [pulled]
  (cond-> (datom/read-blobs pulled)
    (:authz.decision/request pulled)
    (update :authz.decision/request datom/read-blobs)))

(defn decisions
  "Every decision in the ledger, pulled, with EDN blobs read back."
  [{:keys [conn]}]
  (let [d (db/db conn)]
    (mapv #(decode (db/pull d decision-pull %))
          (sort (db/q '[:find [?e ...] :where [?e :authz.decision/decision _]] d)))))

(defn decision
  "One decision by request id, or nil."
  [{:keys [conn]} request-id]
  (let [d (db/db conn)]
    (when-let [e (db/q '[:find ?e . :in $ ?id :where [?e :authz.decision/request-id ?id]]
                       d request-id)]
      (decode (db/pull d decision-pull e)))))

(defn requests
  "Every request in the ledger, including ones not yet decided."
  [{:keys [conn]}]
  (let [d (db/db conn)]
    (mapv #(datom/read-blobs (db/pull d '[*] %))
          (sort (db/q '[:find [?e ...] :where [?e :authz.request/id _]] d)))))

(defn history
  "The journal's own events for this ledger's stream, in the order they were
  appended. The index answers what is true; this answers what happened."
  ([io] (history io default-stream))
  ([io stream] ((:read (journal/journal io)) stream 0)))
