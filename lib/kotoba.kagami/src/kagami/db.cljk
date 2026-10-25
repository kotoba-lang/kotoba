(ns kagami.db
  "genpon（原本）— the pin registry read model (ADR-2607160005 / ADR-2608147300).

  Spoken name: 原本 (genpon). On-disk file: manifest/fleet-db.edn.
  Keys stay :fleet/header :fleet/footer :fleet/remotes :fleet/repos.

  The db value is the map produced by kagami.west/parse:
    {:fleet/header .. :fleet/footer .. :fleet/remotes [..] :fleet/repos [entity ..]}
  persisted as one EDN file. west.yml is the *projection* of this value
  (kagami.west/emit); in Phase 0 the direction of truth is still west.yml ->
  genpon (import), and flips in Phase 1.

  Alongside the db file sits an append-only ledger (one EDN map per line,
  monotonic :event/seq — same shape as canvas-ledger.edn). Phase 0 only
  records events; admission-gate enforcement is Phase 1."
  (:require [kotoba.lang.text :as str]
            [kagami.west :as west]))

(defn schema-datoms
  "The repo-entity schema as Datomic-style transaction maps, for consumers
  that want to transact the db into DataScript/kotobase instead of reading
  the EDN map directly."
  []
  [{:db/ident :repo/name :db/valueType :db.type/string
    :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :repo/remote :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :repo/revision :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :repo/path :db/valueType :db.type/string
    :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :repo/clone-depth :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :repo/groups :db/valueType :db.type/string :db/cardinality :db.cardinality/many}
   {:db/ident :repo/submodules? :db/valueType :db.type/boolean :db/cardinality :db.cardinality/one}])

(defn repo-datoms
  "Repo entities as transactable maps (userdata flattened to :repo/datalad?)."
  [db]
  (mapv (fn [e]
          (cond-> (dissoc e :repo/userdata)
            (get-in e [:repo/userdata :datalad]) (assoc :repo/datalad? true)))
        (:fleet/repos db)))

;; ---------------------------------------------------------------------------
;; queries (plain fns in Phase 0; datalog once fleet-db lives in kotobase)

(defn by-org [db org]
  (filterv #(str/starts-with? (:repo/path %) (str "orgs/" org "/")) (:fleet/repos db)))

(defn by-group [db group]
  (filterv #(some #{group} (:repo/groups %)) (:fleet/repos db)))

(defn heavy [db]      (filterv :repo/clone-depth (:fleet/repos db)))
(defn datalad [db]    (filterv #(get-in % [:repo/userdata :datalad]) (:fleet/repos db)))
(defn archived [db]   (by-group db "archived"))

(defn stats [db]
  {:repos    (count (:fleet/repos db))
   :orgs     (count (:fleet/remotes db))
   :heavy    (count (heavy db))
   :datalad  (count (datalad db))
   :archived (count (archived db))})

;; ---------------------------------------------------------------------------
;; ledger (append-only, one EDN map per line)

(defn next-seq [ledger-events]
  (inc (reduce max 0 (map :event/seq ledger-events))))

(defn pin-advance-event
  "Phase 0 read-model event for a pin advance. `at` is an ISO-8601 string
  supplied by the caller (nbb side owns the clock). Enforcement of the three
  admission invariants is Phase 1; Phase 0 records intent + evidence."
  [ledger-events {:keys [repo old-rev new-rev actor at]}]
  {:event/seq  (next-seq ledger-events)
   :event/type :pin/advance
   :event/at   at
   :event/actor actor
   :repo/name  repo
   :pin/old    old-rev
   :pin/new    new-rev})

(defn apply-pin-advance
  "Apply a pin advance event to the db value (pure)."
  [db event]
  (let [repo-name (:repo/name event)
        new-rev   (:pin/new event)]
    (when-not (west/find-repo db repo-name)
      (throw (ex-info "pin-advance for unknown repo" {:repo repo-name})))
    (update db :fleet/repos
            (fn [repos]
              (mapv #(if (= (:repo/name %) repo-name)
                       (assoc % :repo/revision new-rev)
                       %)
                    repos)))))

;; ---------------------------------------------------------------------------
;; Phase 1.5: reconcile (absorb legacy west.yml writes into fleet-db)

(defn diff-dbs
  "Projection drift between fleet-db and a freshly parsed west.yml.
  -> {:changed [{:name .. :old rev :new rev}] :added [entity ..]
      :removed [name ..] :meta-changed? bool}
  :meta-changed? = header/footer/remotes or non-revision entity fields differ."
  [db-old db-new]
  (let [by-name (fn [d] (into {} (map (juxt :repo/name identity)) (:fleet/repos d)))
        o (by-name db-old) n (by-name db-new)
        names-o (set (keys o)) names-n (set (keys n))
        common (filter #(contains? n %) (map :repo/name (:fleet/repos db-old)))]
    {:changed (into []
                    (keep (fn [nm]
                            (let [ro (o nm) rn (n nm)]
                              (when (not= (:repo/revision ro) (:repo/revision rn))
                                {:name nm :old (:repo/revision ro) :new (:repo/revision rn)}))))
                    common)
     :added   (into [] (keep #(when-not (contains? o (:repo/name %)) %)) (:fleet/repos db-new))
     :removed (into [] (remove names-n) (sort names-o))
     :meta-changed?
     (or (not= (:fleet/header db-old) (:fleet/header db-new))
         (not= (:fleet/footer db-old) (:fleet/footer db-new))
         (some (fn [nm] (not= (dissoc (o nm) :repo/revision)
                              (dissoc (n nm) :repo/revision)))
               common))}))

(defn drift? [{:keys [changed added removed meta-changed?]}]
  (boolean (or (seq changed) (seq added) (seq removed) meta-changed?)))

(defn scope-diff-repos
  "Restrict a diff to a named set of repos (tightest staged-flip scope):
  enforce only the fleet's own signed-path repos while everything else stays
  in absorb mode. Safe first activation — these repos never use the legacy
  path, so enforcing them breaks no concurrent session."
  [diff repo-names]
  (let [in? (set repo-names)]
    {:changed (filterv #(in? (:name %)) (:changed diff))
     :added   (filterv #(in? (:repo/name %)) (:added diff))
     :removed (filterv in? (:removed diff))
     :meta-changed? false}))

(defn scope-diff
  "Restrict a diff to repos under orgs/<org>/ for a set of orgs (staged
  hard flip, D): enforce those orgs while others stay in absorb mode.
  `db-new` resolves paths for :changed entries (which carry only :name)."
  [diff db-new orgs]
  (let [path-of (into {} (map (juxt :repo/name :repo/path)) (:fleet/repos db-new))
        in-scope? (fn [path] (some #(str/starts-with? (str path) (str "orgs/" % "/")) orgs))]
    {:changed (filterv #(in-scope? (path-of (:name %))) (:changed diff))
     :added   (filterv #(in-scope? (:repo/path %)) (:added diff))
     :removed (filterv #(in-scope? (path-of %)) (:removed diff))
     :meta-changed? false}))

(defn reconcile-events
  "Ledger events absorbing legacy-path drift (attributed, unsigned —
  the signed path is the preferred writer; these keep fleet-db lossless)."
  [ledger {:keys [changed added removed]} at]
  (let [base (next-seq ledger)]
    (into []
          (map-indexed (fn [i m] (assoc m :event/seq (+ base i) :event/at at)))
          (concat
           (for [{:keys [name old new]} changed]
             {:event/type :pin/reconcile-legacy :repo/name name
              :pin/old old :pin/new new})
           (for [e added]
             {:event/type :repo/added-legacy :repo/name (:repo/name e)
              :repo/revision (:repo/revision e)})
           (for [nm removed]
             {:event/type :repo/removed-legacy :repo/name nm})))))
