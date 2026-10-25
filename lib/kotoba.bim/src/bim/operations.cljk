(ns bim.operations
  "Tenant-isolated BIM control-plane contracts for scoped access, tamper-
  evident audit, encrypted backups, retention, and disaster recovery."
  (:require [kotoba.lang.coll :as coll]))

(def schema-version 1)
(def role-scopes
  {:viewer #{:project/read}
   :reviewer #{:project/read :issue/read :issue/write}
   :author #{:project/read :project/write :backup/read}
   :manager #{:project/read :project/write :backup/read :backup/write :audit/read
              :tenant/admin}})

(defn control-plane []
  {:operations/schema-version schema-version :operations/tenants {}
   :operations/audit [] :operations/backups {}})

(defn register-tenant [state {:keys [id name administrator timestamp]}]
  (when-not (and id name administrator)
    (throw (ex-info "tenant requires identity, name, and administrator"
                    {:tenant-id id})))
  (if-let [tenant (get-in state [:operations/tenants id])]
    (if (= [name administrator]
           [(:tenant/name tenant) (:tenant/administrator tenant)])
      state
      (throw (ex-info "tenant id already exists" {:tenant-id id})))
    (assoc-in state [:operations/tenants id]
              {:tenant/id id :tenant/name name :tenant/administrator administrator
               :tenant/memberships {administrator :manager}
               :tenant/projects {} :tenant/created-at timestamp})))

(defn issue-principal
  "Issue a serializable, time-bounded principal. Requested scopes may only
  reduce the scopes granted by the actor's tenant role."
  [state tenant-id actor requested-scopes issued-at expires-at]
  (let [role (get-in state [:operations/tenants tenant-id :tenant/memberships actor])
        granted (get role-scopes role #{})
        requested (set requested-scopes)]
    (when-not (and role (number? issued-at) (number? expires-at) (< issued-at expires-at)
                   (coll/subset? requested granted))
      (throw (ex-info "invalid tenant principal request"
                      {:tenant-id tenant-id :actor actor :role role
                       :requested requested :granted granted})))
    {:principal/tenant-id tenant-id :principal/actor actor :principal/role role
     :principal/scopes requested :principal/issued-at issued-at
     :principal/expires-at expires-at}))

(defn- authorize! [state principal scope now]
  (let [tenant-id (:principal/tenant-id principal)
        actor (:principal/actor principal)
        current-role (get-in state [:operations/tenants tenant-id
                                    :tenant/memberships actor])]
    (when-not (and current-role (= current-role (:principal/role principal))
                   (<= (:principal/issued-at principal) now)
                   (< now (:principal/expires-at principal))
                   (contains? (:principal/scopes principal) scope))
      (throw (ex-info "principal is expired, revoked, or outside scope"
                      {:tenant-id tenant-id :actor actor :scope scope :now now})))
    tenant-id))

(defn update-memberships [state principal memberships now]
  (let [tenant-id (authorize! state principal :tenant/admin now)]
    (when-not (some #(= :manager %) (vals memberships))
      (throw (ex-info "tenant must retain a manager" {:tenant-id tenant-id})))
    (assoc-in state [:operations/tenants tenant-id :tenant/memberships] memberships)))

(defn- audit-payload [event]
  [(:audit/sequence event) (:audit/tenant-id event) (:audit/actor event)
   (:audit/action event) (:audit/target event) (:audit/revision event)
   (:audit/timestamp event) (:audit/previous-hash event)])

(defn- append-audit [state digest tenant-id actor action target revision timestamp]
  (let [previous-hash (:audit/hash (peek (:operations/audit state)))
        sequence (inc (count (:operations/audit state)))
        event {:audit/sequence sequence :audit/tenant-id tenant-id
               :audit/actor actor :audit/action action :audit/target target
               :audit/revision revision :audit/timestamp timestamp
               :audit/previous-hash previous-hash}
        hash (digest (pr-str (audit-payload event)))]
    (update state :operations/audit conj (assoc event :audit/hash hash))))

(defn put-project
  "Create or replace a tenant project using optimistic revision control."
  [state principal project-id expected-revision document timestamp digest]
  (let [tenant-id (authorize! state principal :project/write timestamp)
        path [:operations/tenants tenant-id :tenant/projects project-id]
        current (get-in state path)
        head (or (:project/revision current) 0)]
    (if (not= head expected-revision)
      {:operations/status :conflict :operations/state state
       :operations/conflict {:project-id project-id :expected-revision expected-revision
                             :head-revision head}}
      (let [revision (inc head)
            project {:project/id project-id :project/revision revision
                     :project/document document :project/updated-at timestamp
                     :project/updated-by (:principal/actor principal)}
            next-state (-> state (assoc-in path project)
                           (append-audit digest tenant-id (:principal/actor principal)
                                         :project/written [:project project-id]
                                         revision timestamp))]
        {:operations/status (if (zero? head) :created :updated)
         :operations/state next-state :operations/project project}))))

(defn get-project [state principal project-id now]
  (let [tenant-id (authorize! state principal :project/read now)]
    (get-in state [:operations/tenants tenant-id :tenant/projects project-id])))

(defn verify-audit-chain
  "Verify sequence, previous-hash links, and event digests for the full log."
  [state digest]
  (loop [events (:operations/audit state) sequence 1 previous nil]
    (if-let [event (first events)]
      (let [payload (audit-payload event)]
        (if (and (= sequence (:audit/sequence event))
                 (= previous (:audit/previous-hash event))
                 (= (:audit/hash event) (digest (pr-str payload))))
          (recur (next events) (inc sequence) (:audit/hash event))
          {:audit/valid? false :audit/failed-sequence sequence}))
      {:audit/valid? true :audit/events (dec sequence)
       :audit/head-hash previous})))

(defn create-backup
  "Create an encrypted, content-addressed project backup. Crypto, serialization,
  and durable storage remain injected host responsibilities."
  [state principal project-id backup-id timestamp
   {:keys [encode encrypt digest key-id]}]
  (let [tenant-id (authorize! state principal :backup/write timestamp)
        project (get-in state [:operations/tenants tenant-id :tenant/projects project-id])]
    (when-not (and project backup-id encode encrypt digest key-id)
      (throw (ex-info "backup requires a project, id, codecs, digest, and key"
                      {:tenant-id tenant-id :project-id project-id :backup-id backup-id})))
    (when (get-in state [:operations/backups tenant-id backup-id])
      (throw (ex-info "backup id already exists"
                      {:tenant-id tenant-id :backup-id backup-id})))
    (let [plaintext (encode project)
          ciphertext (encrypt key-id plaintext)
          backup {:backup/id backup-id :backup/tenant-id tenant-id
                  :backup/project-id project-id
                  :backup/project-revision (:project/revision project)
                  :backup/created-at timestamp :backup/key-id key-id
                  :backup/content ciphertext :backup/digest (digest ciphertext)}
          next-state (-> state
                         (assoc-in [:operations/backups tenant-id backup-id] backup)
                         (append-audit digest tenant-id (:principal/actor principal)
                                       :backup/created [:backup backup-id]
                                       (:project/revision project) timestamp))]
      {:operations/status :created :operations/state next-state
       :operations/backup (dissoc backup :backup/content)})))

(defn verify-backup [backup digest]
  {:backup/valid? (= (:backup/digest backup) (digest (:backup/content backup)))
   :backup/id (:backup/id backup) :backup/project-revision (:backup/project-revision backup)})

(defn restore-backup
  "Verify, decrypt, and restore into the same tenant. Existing target projects
  require an exact expected revision to prevent accidental overwrite."
  [state principal backup-id target-project-id expected-revision timestamp
   {:keys [decode decrypt digest]}]
  (let [tenant-id (authorize! state principal :backup/write timestamp)
        backup (get-in state [:operations/backups tenant-id backup-id])
        current (get-in state [:operations/tenants tenant-id :tenant/projects
                               target-project-id])
        head (or (:project/revision current) 0)]
    (when-not backup
      (throw (ex-info "backup not found in principal tenant" {:backup-id backup-id})))
    (when-not (:backup/valid? (verify-backup backup digest))
      (throw (ex-info "backup integrity verification failed" {:backup-id backup-id})))
    (if (not= expected-revision head)
      {:operations/status :conflict :operations/state state
       :operations/conflict {:project-id target-project-id
                             :expected-revision expected-revision :head-revision head}}
      (let [restored (decode (decrypt (:backup/key-id backup) (:backup/content backup)))
            revision (inc head)
            project (assoc restored :project/id target-project-id
                           :project/revision revision :project/restored-from backup-id
                           :project/updated-at timestamp
                           :project/updated-by (:principal/actor principal))
            next-state (-> state
                           (assoc-in [:operations/tenants tenant-id :tenant/projects
                                      target-project-id] project)
                           (append-audit digest tenant-id (:principal/actor principal)
                                         :backup/restored [:project target-project-id]
                                         revision timestamp))]
        {:operations/status :restored :operations/state next-state
         :operations/project project}))))

(defn retention-plan
  "Select backups to retain: newest N plus the newest backup in each supplied
  time bucket (for example a day or month key)."
  [backups keep-latest bucket-fn]
  (when-not (and (integer? keep-latest) (<= 0 keep-latest) bucket-fn)
    (throw (ex-info "invalid backup retention policy" {:keep-latest keep-latest})))
  (let [ordered (sort-by :backup/created-at > backups)
        latest (take keep-latest ordered)
        bucketed (vals (reduce (fn [result backup]
                                 (let [bucket (bucket-fn (:backup/created-at backup))]
                                   (if (contains? result bucket) result
                                       (assoc result bucket backup))))
                               {} ordered))
        retained (set (map :backup/id (concat latest bucketed)))]
    {:retention/keep (vec (sort-by str retained))
     :retention/delete (vec (sort-by str
                                    (remove retained (map :backup/id backups))))}))
