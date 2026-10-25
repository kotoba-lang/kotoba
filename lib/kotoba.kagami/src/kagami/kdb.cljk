(ns kagami.kdb
  "kotobase persistence for fleet-db (⑯, ADR-2607160005): project the EDN
  read-model into the real datom plane (kotobase-peer over arrangement/
  chain/prolly-tree), replacing plain-fn queries with Datalog and the
  ~500KB EDN blob with a content-addressed commit chain.

  The EDN model (kagami.west/parse) stays the transport/ingest shape; this
  module is the queryable + persistable projection of it. A contract test
  proves the datom-plane queries equal the EDN-model queries.

  Runs under nbb (kotobase-peer + deps are pure cljc; org-nist-sha2 via
  io-multiformats on the npm path). Persistence (commit!/hydrate) is Promise-returning on
  cljs — callers await. Hot-db transact/query are synchronous."
  (:require [kotobase-peer.core :as kb]
            [kagami.db :as fdb]))

(defn repo->tx
  "One repo entity -> :db/add tx-data (subject = repo path, a stable id)."
  [{:repo/keys [name org path remote revision clone-depth groups submodules? userdata]
    :as e}]
  (let [org* (or org (second (re-find #"orgs/([^/]+)/" (or path ""))))
        s path]
    (cond-> [[:db/add s ":repo/name" name]
             [:db/add s ":repo/path" path]
             [:db/add s ":repo/remote" remote]
             [:db/add s ":repo/revision" revision]]
      org*        (conj [:db/add s ":repo/org" org*])
      clone-depth (conj [:db/add s ":repo/heavy?" true])
      submodules? (conj [:db/add s ":repo/submodules?" true])
      (get userdata :datalad)  (conj [:db/add s ":repo/datalad?" true])
      (get userdata :archived) (conj [:db/add s ":repo/archived?" true])
      (get userdata :rad-rid)  (conj [:db/add s ":repo/rad-rid" (get userdata :rad-rid)])
      :always (into (map (fn [g] [:db/add s ":repo/group" g]) groups)))))

(defn build-db
  "EDN fleet-db -> hot kotobase-peer db (all repos transacted)."
  [fleet-db]
  (kb/transact (kb/empty-db) (mapcat repo->tx (:fleet/repos fleet-db))))

;; ---------------------------------------------------------------------------
;; Datalog queries (replacing kagami.db plain fns)

(defn q-by-org [db org]
  (->> (kb/query db {:find ['?name] :where [['?e ":repo/org" org]
                                            ['?e ":repo/name" '?name]]}
                 (constantly true))
       (map first) sort vec))

(defn q-by-group [db group]
  (->> (kb/query db {:find ['?name] :where [['?e ":repo/group" group]
                                            ['?e ":repo/name" '?name]]}
                 (constantly true))
       (map first) sort vec))

(defn q-heavy [db]
  ;; kotobase-peer stringifies non-Link object values, so booleans persist
  ;; as "true"; query with the string to match the stored datom.
  (->> (kb/query db {:find ['?name] :where [['?e ":repo/heavy?" "true"]
                                            ['?e ":repo/name" '?name]]}
                 (constantly true))
       (map first) sort vec))

(defn q-revision [db repo-name]
  (first (map first
              (kb/query db {:find ['?rev]
                            :where [['?e ":repo/name" repo-name]
                                    ['?e ":repo/revision" '?rev]]}
                        (constantly true)))))

(defn q-count [db] (count (into #{} (map :e) (kb/datoms db (constantly true)))))

;; ---------------------------------------------------------------------------
;; persistence (content-addressed chain; Promise on cljs)

(defn mem-store
  "In-memory block store {:put! :get-fn} backed by an atom (demo/test).
  Production would inject R2/B2/IndexedDB ports."
  []
  (let [m (atom {})]
    {:put! (fn [cid bytes] (swap! m assoc cid bytes) cid)
     :get-fn (fn [cid] (get @m cid))
     :atom m}))

(def id-encrypt #?(:clj identity :cljs (fn [b] (js/Promise.resolve b))))
(def id-decrypt #?(:clj identity :cljs (fn [b] (js/Promise.resolve b))))
(def id-blind   #?(:clj identity :cljs (fn [b] (js/Promise.resolve b))))
