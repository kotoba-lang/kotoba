(ns etzhayyim.ie-flow.ledger
  "ie-flow.ledger — the information-energy flow as an append-only kotoba Datom log. ADR-2606211200.

  The founding design (the user's sketch) puts immutable atomic FACTS — events, nodes, edges,
  stocks, interventions, model runs — in a Datomic-style ledger, and does the CALCULATION in pure
  functions. This is exactly the etzhayyim substrate boundary: canonical state is the kotoba Datom
  log (content-addressed EAVT, append-only 非終末論, ADR-2605312345), and the metric/dynamics/
  co-scientist code is pure folds over it. So the ledger here is the org-native realisation of that
  Datomic-flow ledger: a content-addressed commit-DAG (reusing the shared `kotoba.datom`), with the
  flow ontology as data (schema.edn).

    EVENT        a measured atom of flow: actor moved energy from :source → :target at a :cost,
                 realising :value, at :risk, with :volume (the Sankey backbone)
    NODE         a station in the flow (an organism, agent, page, product, fund…)
    EDGE         an aggregated source→target channel (derived; materialised on read by metrics)
    STOCK        an accumulated order snapshot (subscribers / trust / data-asset / reserves…)
    INTERVENTION a施策 hypothesis the co-scientist pre-registers (dry-run; member-principal outward)

  Append-only (:db/add only — re-measurement is a NEW datom, never an overwrite). Deterministic:
  the caller supplies tx-id + as-of (logical time = log length), so the chain is reproducible and
  crash-resume is byte-identical. No network I/O, no held key (no-server-key)."
  (:require [kotoba.lang.text :as str]
            [kotoba.datom :as kd]))

(def ns-prefix "flow")

;; ── entity ids ──────────────────────────────────────────────────────────────

(defn event-eid       [id] (str ns-prefix ":event:" id))
(defn node-eid        [id] (str ns-prefix ":node:" id))
(defn stock-eid       [as-of] (str ns-prefix ":stock:" as-of))
(defn intervention-eid [id] (str ns-prefix ":intervention:" id))

;; ── value coercion (CID determinism — floats milli-scaled, mirrors react_loop) ──

(defn milli ^long [x] (long (Math/round (* 1000.0 (double x)))))
(defn unmilli [x] (/ (double (long x)) 1000.0))

;; ── projection: domain map → datoms ─────────────────────────────────────────

(defn event-datoms
  "Datoms for one measured flow event. `ev` keys: :id :actor :source :target :type :volume :cost
  :value :risk :agent? (and any :session). Numbers are milli-scaled for content-address stability."
  [ev as-of]
  (let [e (event-eid (:id ev))]
    (cond-> [(kd/add e ":flow.event/id" (str (:id ev)))
             (kd/add e ":flow.event/source" (str (:source ev)))
             (kd/add e ":flow.event/target" (str (:target ev)))
             (kd/add e ":flow.event/type" (str (:type ev)))
             (kd/add e ":flow.event/volume-milli" (milli (:volume ev 0)))
             (kd/add e ":flow.event/cost-milli" (milli (:cost ev 0)))
             (kd/add e ":flow.event/value-milli" (milli (:value ev 0)))
             (kd/add e ":flow.event/risk-milli" (milli (:risk ev 0)))
             (kd/add e ":flow.event/agent" (boolean (:agent? ev)))
             (kd/add e ":flow.event/as-of" as-of)]
      (:actor ev)   (conj (kd/add e ":flow.event/actor" (str (:actor ev))))
      (:session ev) (conj (kd/add e ":flow.event/session" (str (:session ev)))))))

(defn node-datoms
  "Datoms for one flow node. `n` keys: :id :node-type :name."
  [n as-of]
  (let [e (node-eid (:id n))]
    [(kd/add e ":flow.node/id" (str (:id n)))
     (kd/add e ":flow.node/type" (str (:node-type n)))
     (kd/add e ":flow.node/name" (str (:name n (:id n))))
     (kd/add e ":flow.node/as-of" as-of)]))

(defn stock-datoms
  "Datoms for one accumulated-order snapshot. `s` = a map of order-name → numeric value."
  [s as-of]
  (let [e (stock-eid as-of)]
    (conj (vec (for [[k v] (sort-by (comp str key) s)]
                 (kd/add e (str ":flow.stock/" (name k)) (milli v))))
          (kd/add e ":flow.stock/as-of" as-of))))

(defn intervention-datoms
  "Datoms for one pre-registered施策. `iv` keys: :id :itype :name :target :hypothesis :status."
  [iv as-of]
  (let [e (intervention-eid (:id iv))]
    [(kd/add e ":flow.intervention/id" (str (:id iv)))
     (kd/add e ":flow.intervention/type" (str (:itype iv)))
     (kd/add e ":flow.intervention/name" (str (:name iv)))
     (kd/add e ":flow.intervention/target" (str (:target iv)))
     (kd/add e ":flow.intervention/hypothesis" (str (:hypothesis iv)))
     (kd/add e ":flow.intervention/status" (str (:status iv "dry-run")))
     (kd/add e ":flow.intervention/as-of" as-of)]))

;; ── as-of reader (datoms → event maps; the inverse of event-datoms) ─────────

(defn- all-datoms [txs] (for [tx txs d (:tx/datoms tx)] d))

(defn fold-entity
  "Latest attr→value map for one entity (append-only fold)."
  [txs entity]
  (reduce (fn [out [_op e a v]] (if (= e entity) (assoc out a v) out))
          {}
          (all-datoms txs)))

(defn entities-with
  "Every entity (first-assertion order, deduped) carrying `attr`."
  [txs attr]
  (second
   (reduce (fn [[seen order :as acc] [_op e a _v]]
             (if (and (= a attr) (not (seen e))) [(conj seen e) (conj order e)] acc))
           [#{} []]
           (all-datoms txs))))

(defn read-events
  "Materialise every flow EVENT on the log back into the metric-ready event maps (numbers
  un-milli'd). Deterministic, ordered by first assertion. Pure over `txs`."
  [txs]
  (mapv (fn [e]
          (let [m (fold-entity txs e)]
            {:id (get m ":flow.event/id")
             :actor (get m ":flow.event/actor")
             :source (get m ":flow.event/source")
             :target (get m ":flow.event/target")
             :type (get m ":flow.event/type")
             :volume (unmilli (get m ":flow.event/volume-milli" 0))
             :cost (unmilli (get m ":flow.event/cost-milli" 0))
             :value (unmilli (get m ":flow.event/value-milli" 0))
             :risk (unmilli (get m ":flow.event/risk-milli" 0))
             :agent? (boolean (get m ":flow.event/agent"))}))
        (entities-with txs ":flow.event/id")))

(defn read-stock
  "Latest accumulated-order snapshot on the log (the most recently asserted :flow.stock entity),
  un-milli'd → a plain order-name→value map. nil if none."
  [txs]
  (when-let [e (last (entities-with txs ":flow.stock/as-of"))]
    (let [m (fold-entity txs e)]
      (reduce-kv (fn [out a v]
                   (if (and (str/starts-with? (str a) ":flow.stock/")
                            (not= a ":flow.stock/as-of"))
                     (assoc out (keyword (subs (str a) (count ":flow.stock/"))) (unmilli v))
                     out))
                 {}
                 m))))

;; ── append (idempotent-by-content; the kaname/ibuki commit-DAG pattern) ─────

#?(:clj
   (defn append!
     "Append one content-addressed tx of `datoms` to the commit-DAG at `log-path`, idempotent by
     content (a tx whose datoms equal the last tx's is a no-op). Returns {:head :appended :count}."
     [datoms {:keys [log-path tx-id as-of]}]
     (let [txs (kd/read-log log-path)
           prev (kd/head-cid log-path)
           last-ds (some-> (peek txs) :tx/datoms)
           base {:count (count datoms) :head prev}]
       (if (and (seq datoms) (= (kd/normalize-datoms datoms) last-ds))
         (assoc base :appended false :reason :no-change)
         (let [tx (kd/make-tx datoms {:tx-id tx-id :as-of as-of :prev-cid prev})]
           (kd/append-tx! tx log-path)
           (assoc base :appended true :head (:tx/cid tx)))))))

#?(:clj
   (defn record-events!
     "Append a batch of measured flow EVENTS as one tx. Returns the append result."
     [events {:keys [log-path tx-id as-of]}]
     (append! (vec (mapcat #(event-datoms % as-of) events))
              {:log-path log-path :tx-id tx-id :as-of as-of})))
