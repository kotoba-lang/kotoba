(ns browser.persistence
  "Persistence adapter contract for profile, storage, and audit state.")

(def current-version 3)

(def migrations
  [{:migration/from 1
    :migration/to 2
    :migration/steps [:rename-snapshot-store-to-storage
                      :wrap-history-and-navigation-in-session]}
   {:migration/from 2
    :migration/to 3
    :migration/steps [:add-surface-snapshot]}])

(defn migration-plan
  ([]
   (migration-plan 1 current-version))
  ([from-version to-version]
   (vec (filter (fn [{:migration/keys [from to]}]
                  (and (<= (or from-version 1) from)
                       (<= to to-version)))
                migrations))))

(defn profile-datoms
  [profile]
  (let [eid (str "browser.profile/" (:profile/id profile))]
    (cond-> [[:db/add eid :profile/id (:profile/id profile)]
             [:db/add eid :profile/account-id (:profile/account-id profile)]
             [:db/add eid :profile/name (:profile/name profile)]
             [:db/add eid :profile/storage-partition (:profile/storage-partition profile)]]
      (seq (:profile/history profile))
      (into (map-indexed (fn [idx entry]
                           [:db/add eid :profile/history [idx entry]])
                         (:profile/history profile))))))

(defn storage-datoms
  [store]
  (vec
   (for [[[partition origin k] v] (tree-seq map? vals (:storage/data store))
         :when false]
     [:db/add partition origin [k v]])))

(defn storage-entry-datoms
  [store]
  (letfn [(walk [path x]
            (if (map? x)
              (mapcat (fn [[k v]] (walk (conj path k) v)) x)
              [(let [[partition origin k] path]
                 [:db/add (str "browser.storage/" partition "/" origin)
                  :storage/entry {:partition partition :origin origin :key k :value x}])]))]
    (vec (walk [] (:storage/data store)))))

(defn audit-datoms
  [audit]
  (:audit/datoms audit))

(defn session-datoms
  [session]
  (vec
   (concat
    (map-indexed (fn [idx entry]
                   [:db/add "browser.session/current" :session/history [idx entry]])
                 (:history session))
    (map-indexed (fn [idx entry]
                   [:db/add "browser.session/current" :navigation/entry
                    [idx (select-keys entry [:url])]])
                 (get-in session [:navigation :entries]))
    (when-let [idx (get-in session [:navigation :index])]
      [[:db/add "browser.session/current" :navigation/index idx]])
    (map-indexed (fn [idx redirect]
                   [:db/add "browser.session/current" :navigation/redirect [idx redirect]])
                 (get-in session [:navigation :redirects])))))

(defn surface-datoms
  [surface]
  (let [eid (str "browser.surface/" (:surface/id surface))]
    (vec
     (concat
      [[:db/add eid :surface/id (:surface/id surface)]
       [:db/add eid :surface/title (:surface/title surface)]
       [:db/add eid :surface/focus (:surface/focus surface)]
       [:db/add eid :surface/window-count (count (:surface/windows surface))]]
      (map-indexed
       (fn [idx window]
         [:db/add eid :surface/window
          [idx (select-keys window [:window/id
                                    :window/app-id
                                    :window/title
                                    :window/rect
                                    :window/state
                                    :window/text-buffer
                                    :window/scroll])]])
       (:surface/windows surface))))))

(defn snapshot
  [{:keys [profile store audit chrome surface session]}]
  (let [session (or session {:history []
                             :navigation {:entries [] :index -1 :redirects []}})]
    {:snapshot/version current-version
     :snapshot/profile profile
     :snapshot/storage store
     :snapshot/audit audit
     :snapshot/chrome chrome
     :snapshot/surface surface
     :snapshot/session session
     :snapshot/datoms (vec (concat (when profile (profile-datoms profile))
                                   (when store (storage-entry-datoms store))
                                   (when audit (audit-datoms audit))
                                   (when surface (surface-datoms surface))
                                   (session-datoms session)))}))

(defn migrate-snapshot
  "Normalizes older snapshot shapes into the current snapshot schema."
  [snapshot]
  (when snapshot
    (let [version (or (:snapshot/version snapshot) 1)
          plan (migration-plan version current-version)
          snapshot (cond-> snapshot
                     (:snapshot/store snapshot)
                     (assoc :snapshot/storage (:snapshot/store snapshot))

                     (not (vector? (:snapshot/datoms snapshot)))
                     (assoc :snapshot/datoms [])

                     (not (:snapshot/session snapshot))
                     (assoc :snapshot/session
                            {:history (or (:snapshot/history snapshot) [])
                             :navigation (or (:snapshot/navigation snapshot)
                                             {:entries [] :index -1 :redirects []})})

                     (not (contains? snapshot :snapshot/surface))
                     (assoc :snapshot/surface nil))]
      (-> snapshot
          (dissoc :snapshot/store :snapshot/history :snapshot/navigation)
          (assoc :snapshot/version current-version)
          (cond-> (not= version current-version)
            (assoc :snapshot/migrated-from version
                   :snapshot/migration-plan plan))))))

(defn validate-snapshot
  [snapshot]
  (let [errors (cond-> []
                 (not= current-version (:snapshot/version snapshot))
                 (conj {:error :snapshot/version-mismatch
                        :expected current-version
                        :actual (:snapshot/version snapshot)})

                 (contains? snapshot :snapshot/store)
                 (conj {:error :snapshot/legacy-store-key})

                 (not (map? (:snapshot/session snapshot)))
                 (conj {:error :snapshot/session-missing})

                 (not (vector? (get-in snapshot [:snapshot/session :history])))
                 (conj {:error :snapshot/session-history-not-vector})

                 (not (map? (get-in snapshot [:snapshot/session :navigation])))
                 (conj {:error :snapshot/navigation-missing})

                 (not (vector? (:snapshot/datoms snapshot)))
                 (conj {:error :snapshot/datoms-not-vector}))]
    {:valid? (empty? errors)
     :errors errors}))

(defn migration-report
  [before after]
  {:migration/from (or (:snapshot/version before) 1)
   :migration/to (:snapshot/version after)
   :migration/plan (:snapshot/migration-plan after)
   :migration/valid? (:valid? (validate-snapshot after))
   :migration/errors (:errors (validate-snapshot after))})

(defn replay-session
  [snapshot]
  (let [snapshot (migrate-snapshot snapshot)]
    {:history (get-in snapshot [:snapshot/session :history] [])
     :navigation (merge {:entries [] :index -1 :redirects []}
                        (get-in snapshot [:snapshot/session :navigation]))}))

(defn adapter-contract
  []
  {:persistence/imports #{:storage/get :storage/put :storage/delete :log/write}
   :persistence/exports #{:persistence/save-snapshot
                          :persistence/load-snapshot
                          :persistence/migrate-snapshot
                          :persistence/append-datoms}
   :persistence/no-ambient-access true})
