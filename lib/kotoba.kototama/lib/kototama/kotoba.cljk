(ns kototama.kotoba
  "kototama · kotoba substrate — the append-only, content-addressed Datom log
  that every cell / artificial organism persists on. The distilled, dependency-
  free subset of `etzhayyim.kotoba.engine` + `ibuki.methods.datoms`: enough to
  connect, transact (append-only EAVT), query, snapshot as-of, and verify the
  commit-DAG — pure `.cljc` so it runs on bb / JVM AND inside the kototama
  Rust→WASM runtime (no java.security, no wall-clock, no 3rd-party deps).

  A transaction is content-addressed: its id is a deterministic digest of its
  datoms + parent, so the log is a tamper-evident commit-DAG and `append-tx!` is
  idempotent-by-content (re-appending the same tx is a no-op → crash-resume is
  byte-identical). The in-process digest here is FNV-1a over the canonical
  pr-str (portable, stable); the LIVE kotoba engine uses a real CIDv1
  (dag-cbor/sha2-256) — bridge via `kototama.kotoba/->bridge-edn` + the host's
  kotoba_bridge. The two agree on *structure*, not byte-for-byte CID; that is the
  documented seam."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────── content addressing ─────────────────────────

(defn- fnv1a
  "FNV-1a 64-bit over the codepoints of s (portable; no byte API). Uses
  unchecked-multiply so the 2^64 wraparound the hash relies on does not throw."
  [s]
  (let [prime 1099511628211]
    (reduce (fn [h c] (unchecked-multiply (bit-xor h (long c)) prime))
            (unchecked-long 1469598103934665603)
            (map int (seq s)))))

(defn content-id
  "Deterministic content digest of any EDN value → \"b<hex>\". Stable across bb
  runs and platforms. NOT a CIDv1 (the live engine computes that); it is the
  in-process tamper-evident address."
  [v]
  (str "b" (-> (fnv1a (pr-str v)) (Long/toUnsignedString 16))))

;; ───────────────────────── transactions ─────────────────────────

(defn make-tx
  "Build a content-addressed tx. `datoms` is a vector of [:db/add e a v].
  opts: :prev (parent tx-id, defaults nil), :as-of (caller-supplied logical
  clock int — kept out of the digest's *identity* contribution beyond the
  datoms+prev so identical facts on the same parent collapse)."
  [datoms & [{:keys [prev as-of meta]}]]
  (let [body {:tx/datoms (vec datoms) :tx/prev prev}]
    (cond-> (assoc body :tx/cid (content-id body))
      as-of (assoc :tx/as-of as-of)
      meta  (assoc :tx/meta meta))))

;; ───────────────────────── connection (in-process log) ─────────────────────────

(defn connect
  "Open an in-process connection. opts: :log (seed vector of txs, default [])."
  [& [{:keys [log]}]]
  (atom {:log (vec (or log []))}))

(defn log [conn] (:log @conn))
(defn head-cid [conn] (-> @conn :log peek :tx/cid))

(defn append-tx!
  "Append a tx, idempotent-by-content: if a tx with the same :tx/cid is already
  the head, it is a no-op (returns the unchanged head). Returns
  {:tx tx :head-cid cid :appended? bool}."
  [conn tx]
  (let [cur (head-cid conn)]
    (if (= cur (:tx/cid tx))
      {:tx tx :head-cid cur :appended? false}
      (do (swap! conn update :log conj tx)
          {:tx tx :head-cid (:tx/cid tx) :appended? true}))))

(defn transact
  "Append datoms as a new tx chained onto the current head. Returns
  {:tx :head-cid :datoms :appended?}."
  [conn datoms & [{:keys [as-of meta]}]]
  (let [tx (make-tx datoms {:prev (head-cid conn) :as-of as-of :meta meta})]
    (merge (append-tx! conn tx) {:datoms (:tx/datoms tx)})))

;; ───────────────────────── query / as-of ─────────────────────────

(defn- apply-datom [eav [op e a v]]
  (case op
    :db/add     (assoc-in eav [e a] v)
    :db/retract (update eav e dissoc a)
    eav))

(defn db
  "Materialize the EAVT log into {entity {attr value}} by replaying all datoms."
  [conn]
  (reduce (fn [eav tx] (reduce apply-datom eav (:tx/datoms tx)))
          {} (log conn)))

(defn as-of
  "The materialized db after the first `n` transactions (replay-deterministic;
  the basis for crash-resume + 'mood at beat N')."
  [conn n]
  (reduce (fn [eav tx] (reduce apply-datom eav (:tx/datoms tx)))
          {} (take n (log conn))))

(defn entity [conn e] (get (db conn) e))

(defn where
  "Entities whose attribute `a` equals `v` → seq of [e attrs]."
  [conn a v]
  (filter (fn [[_ attrs]] (= v (get attrs a))) (db conn)))

(defn datoms
  "All datoms across the log, oldest→newest (flattened)."
  [conn]
  (into [] (mapcat :tx/datoms) (log conn)))

;; ───────────────────────── integrity ─────────────────────────

(defn verify-chain
  "Tamper-evident check: every tx's :tx/cid must equal the recomputed digest of
  its body, and :tx/prev must chain to the predecessor's :tx/cid. Returns
  {:ok? bool :at idx-or-nil :reason kw-or-nil}."
  [conn]
  (loop [txs (log conn) parent nil idx 0]
    (if-let [{:tx/keys [datoms prev cid]} (first txs)]
      (let [recomputed (content-id {:tx/datoms datoms :tx/prev prev})]
        (cond
          (not= cid recomputed) {:ok? false :at idx :reason :cid-mismatch}
          (not= prev parent)    {:ok? false :at idx :reason :broken-link}
          :else                 (recur (rest txs) cid (inc idx))))
      {:ok? true :at nil :reason nil})))

;; ───────────────────────── live-engine bridge seam ─────────────────────────

(defn ->bridge-edn
  "Render a tx as the EDN datom-vector the live kotoba engine ingests
  (`com.etzhayyim.apps.kotoba.datomic.transact`). The host's kotoba_bridge adds
  the real CIDv1 + provenance; this lib stays transport-free (no I/O, no key)."
  [tx]
  {:tx_edn (pr-str (:tx/datoms tx))
   :local_cid (:tx/cid tx)
   :local_prev (:tx/prev tx)})
