;; etzhayyim.kotoba.engine — public root-side Datom-log API.
;;
;; This is the runnable interim substrate the actors talk to TODAY, replacing
;; the 40-engine/datomic_emulator.py stub (whose q() always returned []). It is
;; the root-side realization of ADR-2605262130 Phase 1/2 (store + kqe-style
;; arrangement + Datalog read) — the kotoba subrepo stays the generic Rust
;; engine; all data + this glue live in root.
;;
;; Usage:
;;   (require '[etzhayyim.kotoba.engine :as kt])
;;   (def conn (kt/connect {:journal "80-data/datomic_mock/journal.edn"
;;                          :schemas ["00-contracts/schemas/unspsc-ontology.kotoba.edn"]}))
;;   (kt/transact conn [{:db/id "ch_123" :stripe.Charge/amount 500}])
;;   (kt/q conn '{:find [?e ?amt]
;;                :where [[?e :stripe.Charge/amount ?amt]]})
;;   (kt/head-cid conn)   ; content-address of the journal head

(ns etzhayyim.kotoba.engine
  (:require [kotoba.lang.text :as str]
            [etzhayyim.kotoba.datom :as d]
            [etzhayyim.kotoba.log :as log]
            [etzhayyim.kotoba.query :as query]
            [etzhayyim.kotoba.schema :as schema]
            [etzhayyim.kotoba.encrypted :as enc]
            [etzhayyim.kotoba.cid :as cid]))

(defn connect
  "Open a connection over a journal file. opts:
     :journal   path to the EDN-lines journal (default 80-data/datomic_mock/journal.edn)
     :schemas   seq of .kotoba.edn schema paths to load (optional)
     :validate? when true, transact rejects any datom whose value violates the
                schema's declared :db/valueType / :db/allowed (default false —
                open-world, preserves untyped-actor ingest)
   Returns an atom holding {:journal :attrs :validate? :log}."
  [{:keys [journal schemas validate?] :or {journal log/default-journal}}]
  (let [attrs (apply schema/merge-schemas (map schema/load-schema schemas))
        l (log/read-log (log/ensure-journal! journal))]
    (atom {:journal journal :attrs attrs :validate? (boolean validate?) :log l})))

(defn db
  "Current immutable database value: live triples + four-index arrangement."
  [conn]
  (let [{:keys [log]} @conn
        live (d/live-datoms log)]
    {:live live :index (d/index live) :log log}))

(defn- map->adds
  "Turn a {:db/id e, :attr v, ...} entity map into a seq of {:e :a :v} adds.
   For cardinality-many a vector/set value expands to one add per element."
  [attrs m]
  (let [e (:db/id m)]
    (when (nil? e) (throw (ex-info "entity map needs :db/id" {:map m})))
    (for [[a v] (dissoc m :db/id)
          v* (if (and (not (schema/one? attrs a)) (coll? v)) v [v])]
      {:e e :a a :v v*})))

(defn transact
  "Commit tx-data and append to the journal. tx-data is a seq of:
     - entity maps {:db/id e :ns/attr v ...}
     - raw datom vectors [e a v] / [e a v tx op]
   Returns {:tx :datoms :head} with the new head CID."
  [conn tx-data]
  (let [{:keys [journal attrs validate? log]} @conn
        tx (inc (log/max-tx log))
        live (d/live-datoms log)
        adds (mapcat (fn [item]
                       (cond
                         (map? item) (map->adds attrs item)
                         (vector? item) [{:e (d/d-e item) :a (d/d-a item) :v (d/d-v item)}]
                         :else (throw (ex-info "bad tx item" {:item item}))))
                     tx-data)
        expanded (vec (schema/expand-tx attrs live tx adds))]
    ;; transact-time validation hook: reject the WHOLE tx before any write if a
    ;; new assertion violates the schema's declared type/enum, OR a unique
    ;; (:db.unique/identity|value) value would be claimed by a second entity
    ;; (atomic; the bad datom never reaches the durable log).
    (when validate?
      (let [viols (keep #(when (d/assert? %) (schema/check-datom-value attrs %)) expanded)
            confs (schema/unique-conflicts attrs live adds)]
        (when (or (seq viols) (seq confs))
          (throw (ex-info "schema validation failed; tx rejected (nothing written)"
                          (cond-> {:tx tx}
                            (seq viols) (assoc :violations (vec viols))
                            (seq confs) (assoc :unique-conflicts (vec confs))))))))
    (let [new-log (into log expanded)]
      (log/append! journal expanded)
      (swap! conn assoc :log new-log)
      {:tx tx :datoms (count expanded) :head (log/head-cid new-log)})))

(defn q
  "Datalog query against the current db. See etzhayyim.kotoba.query/q."
  [conn query-map & inputs]
  (apply query/q query-map (:live (db conn)) inputs))

(defn entity
  "Pull all current attributes of entity `e` into a map (incl :db/id)."
  [conn e]
  (let [{:keys [index]} (db conn)]
    (into {:db/id e}
          (for [[a vs] (get-in index [:eavt e])]
            [a (if (= 1 (count vs)) (first vs) vs)]))))

(defn pull
  "Datomic-style pull: fetch entity `eid` shaped by `pattern`, recursing into
   referenced entities. Pattern elements:
     :attr             include that attribute's value
     '*                include all of the entity's attributes (no recursion)
     {:ref-attr sub}   follow :ref-attr's value(s) as entity ids, pull each w/ `sub`
     {:ns/_back sub}   REVERSE ref: pull every entity that points HERE via :ns/back
                       (VAET navigation) — always a vector
   Recursion is bounded by the pattern depth (cycle-safe). A forward ref value
   with no datoms is kept as the raw id. Returns a map (with :db/id), or nil if
   `eid` has no datoms (forward) — reverse-only entities still resolve."
  [conn eid pattern]
  (let [{:keys [index]} (db conn)
        amap (get-in index [:eavt eid])
        scalar (fn [vs] (if (= 1 (count vs)) (first vs) (vec vs)))
        reverse? (fn [a] (str/starts-with? (name a) "_"))
        forward-of (fn [a] (keyword (namespace a) (subs (name a) 1)))
        result
        (reduce
         (fn [acc spec]
           (cond
             (= '* spec) (reduce (fn [m [a vs]] (assoc m a (scalar vs))) acc amap)
             (keyword? spec) (if-let [vs (get amap spec)] (assoc acc spec (scalar vs)) acc)
             (map? spec)
             (reduce-kv
              (fn [m ref-attr sub]
                (if (reverse? ref-attr)
                  (let [back (get-in index [:vaet eid (forward-of ref-attr)])]
                    (if (seq back)
                      (assoc m ref-attr (mapv #(or (pull conn % sub) %) (sort back)))
                      m))
                  (if-let [vs (get amap ref-attr)]
                    (assoc m ref-attr (scalar (mapv #(or (pull conn % sub) %) vs)))
                    m)))
              acc spec)
             :else acc))
         {:db/id eid}
         pattern)]
    ;; nil when nothing beyond :db/id resolved (unknown / empty entity)
    (when (not= result {:db/id eid}) result)))

(defn as-of
  "Time-travel: live triples considering only datoms with tx <= `t`."
  [conn t]
  (let [{:keys [log]} @conn]
    (d/live-datoms (filter #(<= (d/d-tx %) t) log))))

;; ── confidential datoms (ADR-2605181100 envelope on the ADR-2605262130 log) ──
;; Integrates increment #1 (log) + #2 (envelope): a confidential record is sealed
;; into a com.etzhayyim.encrypted.record and stored AS datoms — only the
;; ciphertext envelope (+ its CID + per-recipient keyWraps) ever touch the log;
;; the plaintext does not. Hot-path queries see the envelope CID; only a
;; key-holder can `read-encrypted`.

(defn transact-encrypted
  "Seal `plaintext` under `sym-key`+`nonce24` and store it on entity `e` as:
     [e :enc/envelope <env>] [e :enc/cid <cid>] [e :enc/innerType <t>]
     + one keyWrap entity per recipient.
   opts: :sender :innerType :createdAt :recipients. Returns {:tx :cid :head}."
  [conn ^bytes sym-key ^bytes nonce24 e plaintext
   {:keys [sender innerType createdAt recipients]}]
  (let [env (enc/seal sym-key nonce24 plaintext
                      {:sender sender :innerType innerType :createdAt createdAt})
        ecid (enc/envelope-cid env)
        wrap-entities
        (map-indexed
         (fn [i r]
           (let [kw (enc/key-wrap sym-key {:sender sender :recipient r
                                           :signalSessionId (str "sess:" r)
                                           :createdAt createdAt
                                           :recordUri (str "at://" e)})]
             {:db/id (str ecid "#kw" i)
              :enc.keyWrap/of ecid
              :enc.keyWrap/recipient r
              :enc.keyWrap/record kw}))
         recipients)
        res (transact conn (cons {:db/id e :enc/envelope env
                                  :enc/cid ecid :enc/innerType innerType}
                                 wrap-entities))]
    (assoc res :cid ecid)))

(defn read-encrypted
  "Decrypt the confidential record stored on entity `e` with `sym-key`.
   Throws if the key is wrong or the envelope was tampered (AEAD failure)."
  [conn ^bytes sym-key e]
  (let [env (:enc/envelope (entity conn e))]
    (when (nil? env)
      (throw (ex-info "no encrypted record on entity" {:e e})))
    (enc/open sym-key env)))

(defn recipients-of
  "DIDs that hold a keyWrap (read-cap) for envelope CID `ecid`."
  [conn ecid]
  (mapv first (q conn '{:find [?r] :in [?cid]
                        :where [[?kw :enc.keyWrap/of ?cid]
                                [?kw :enc.keyWrap/recipient ?r]]}
                 ecid)))

(defn head-cid [conn] (log/head-cid (:log @conn)))

(defn snapshot!
  "Materialize current live state to a canonical .kotoba.edn vector file."
  [conn out-path & opts]
  (apply log/snapshot->kotoba-edn! (:log @conn) out-path opts))
