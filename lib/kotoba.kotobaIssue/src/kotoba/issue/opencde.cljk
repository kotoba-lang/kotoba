(ns kotoba.issue.opencde
  "Transport-neutral OpenCDE-compatible project, document, and BCF topic
  service. HTTP adapters can expose these pure operations without coupling the
  shared contract to a server framework or database."
  (:require [kotoba.lang.text :as string]
            [kotoba.issue.bcf :as bcf]))

(def contract-version 1)
(def api-versions
  [{:api-id "foundation" :version-id "1.0" :status "stable"}
   {:api-id "bcf" :version-id "3.0" :status "stable"}
   {:api-id "documents" :version-id "1.0" :status "stable"}])

(def role-capabilities
  {:viewer #{:project/read :document/read :topic/read}
   :reviewer #{:project/read :document/read :topic/read :topic/write}
   :editor #{:project/read :document/read :document/write :topic/read :topic/write}
   :admin #{:project/read :project/admin :document/read :document/write
            :topic/read :topic/write :audit/read}})

(defn service-info
  "OpenCDE foundation discovery payload. Base URLs are supplied by the host."
  [{:keys [name base-url auth-url]}]
  {:opencde/contract-version contract-version
   :name (or name "Kotoba Common Data Environment")
   :base-url base-url :authentication-url auth-url
   :versions api-versions})

(defn store []
  {:opencde/contract-version contract-version
   :opencde/projects {} :opencde/audit [] :opencde/idempotency {}})

(defn- membership [state project-id actor]
  (get-in state [:opencde/projects project-id :project/memberships actor]))

(defn authorized? [state project-id actor capability]
  (contains? (get role-capabilities (membership state project-id actor) #{})
             capability))

(defn- require-authorized! [state project-id actor capability]
  (when-not (authorized? state project-id actor capability)
    (throw (ex-info "OpenCDE actor is not authorized"
                    {:project-id project-id :actor actor :capability capability}))))

(defn- audit [state project-id actor action target revision timestamp]
  (update state :opencde/audit conj
          {:audit/sequence (inc (count (:opencde/audit state)))
           :audit/project-id project-id :audit/actor actor :audit/action action
           :audit/target target :audit/revision revision :audit/timestamp timestamp}))

(defn register-project
  "Register a project and its role memberships. Repeating the same request is
  idempotent; changing an existing project id is rejected."
  [state actor {:keys [id name memberships metadata timestamp] :as request}]
  (when-not (and id name (= :admin (get memberships actor)))
    (throw (ex-info "OpenCDE project requires an admin creator"
                    {:actor actor :request request})))
  (if-let [existing (get-in state [:opencde/projects id])]
    (if (= (select-keys existing [:project/id :project/name :project/memberships
                                  :project/metadata])
           {:project/id id :project/name name :project/memberships memberships
            :project/metadata (or metadata {})})
      state
      (throw (ex-info "OpenCDE project id already exists" {:project-id id})))
    (-> state
        (assoc-in [:opencde/projects id]
                  {:project/id id :project/name name
                   :project/metadata (or metadata {})
                   :project/memberships memberships
                   :project/documents {} :project/topics {} :project/revision 0})
        (audit id actor :project/created [:project id] 0 timestamp))))

(defn update-memberships [state project-id actor memberships timestamp]
  (require-authorized! state project-id actor :project/admin)
  (when-not (some #(= :admin %) (vals memberships))
    (throw (ex-info "OpenCDE project must retain an administrator"
                    {:project-id project-id})))
  (-> state
      (assoc-in [:opencde/projects project-id :project/memberships] memberships)
      (audit project-id actor :project/memberships-updated
             [:project project-id] nil timestamp)))

(defn- idempotent-result [state project-id key request]
  (when-let [record (get-in state [:opencde/idempotency [project-id key]])]
    (if (= request (:request record))
      (:result record)
      (throw (ex-info "OpenCDE idempotency key conflicts with prior request"
                      {:project-id project-id :idempotency-key key})))))

(defn- remember [state project-id key request result]
  (assoc-in state [:opencde/idempotency [project-id key]]
            {:request request :result (assoc result :opencde/state nil)}))

(defn put-document
  "Create a new immutable document version. `base-version` must equal the
  current head (zero for a new document), providing OpenCDE optimistic
  concurrency. Content remains external and is addressed by reference/hash."
  [state project-id actor
   {:keys [document-id name media-type content-ref content-hash base-version
           idempotency-key metadata timestamp]
    :as request}]
  (require-authorized! state project-id actor :document/write)
  (when-not (and document-id name media-type content-ref content-hash
                 idempotency-key (integer? base-version) (<= 0 base-version))
    (throw (ex-info "invalid OpenCDE document version request" {:request request})))
  (if-let [cached (idempotent-result state project-id idempotency-key request)]
    (assoc cached :opencde/state state :opencde/status :deduplicated)
    (let [document (get-in state [:opencde/projects project-id :project/documents
                                  document-id])
          head (or (:document/head-version document) 0)]
      (if (not= head base-version)
        {:opencde/status :conflict :opencde/state state
         :opencde/conflict {:document-id document-id :base-version base-version
                            :head-version head}}
        (let [version (inc head)
              value {:document/id document-id :document/version version
                     :document/name name :document/media-type media-type
                     :document/content-ref content-ref :document/content-hash content-hash
                     :document/metadata (or metadata {}) :document/created-by actor
                     :document/created-at timestamp}
              next-state (-> state
                             (assoc-in [:opencde/projects project-id :project/documents
                                        document-id :document/id] document-id)
                             (assoc-in [:opencde/projects project-id :project/documents
                                        document-id :document/head-version] version)
                             (assoc-in [:opencde/projects project-id :project/documents
                                        document-id :document/versions version] value)
                             (update-in [:opencde/projects project-id :project/revision] inc)
                             (audit project-id actor :document/version-created
                                    [:document document-id] version timestamp))
              result {:opencde/status :created :opencde/document value}
              next-state (remember next-state project-id idempotency-key request result)]
          (assoc result :opencde/state next-state))))))

(defn get-document
  ([state project-id actor document-id]
   (let [head (get-in state [:opencde/projects project-id :project/documents
                             document-id :document/head-version])]
     (get-document state project-id actor document-id head)))
  ([state project-id actor document-id version]
   (require-authorized! state project-id actor :document/read)
   (get-in state [:opencde/projects project-id :project/documents
                  document-id :document/versions version])))

(defn list-documents [state project-id actor]
  (require-authorized! state project-id actor :document/read)
  (->> (get-in state [:opencde/projects project-id :project/documents])
       vals
       (mapv (fn [document]
               (get-in document [:document/versions (:document/head-version document)])))
       (sort-by (juxt :document/name :document/id)) vec))

(defn put-topic
  "Create or replace a BCF 3.0 topic at an expected revision. The normalized
  topic is validated by the shared BCF contract before it becomes visible."
  [state project-id actor
   {:keys [topic expected-revision idempotency-key timestamp] :as request}]
  (require-authorized! state project-id actor :topic/write)
  (when-not (and idempotency-key (integer? expected-revision)
                 (<= 0 expected-revision))
    (throw (ex-info "invalid OpenCDE BCF topic request" {:request request})))
  (if-let [cached (idempotent-result state project-id idempotency-key request)]
    (assoc cached :opencde/state state :opencde/status :deduplicated)
    (let [topic (if (:bcf.topic/guid topic) topic (bcf/topic topic))
          topic-id (:bcf.topic/guid topic)
          current (get-in state [:opencde/projects project-id :project/topics topic-id])
          head (or (:topic/revision current) 0)]
      (if (not= head expected-revision)
        {:opencde/status :conflict :opencde/state state
         :opencde/conflict {:topic-guid topic-id :expected-revision expected-revision
                            :head-revision head}}
        (let [revision (inc head)
              value {:topic/revision revision :topic/value topic
                     :topic/updated-by actor :topic/updated-at timestamp}
              next-state (-> state
                             (assoc-in [:opencde/projects project-id :project/topics topic-id]
                                       value)
                             (update-in [:opencde/projects project-id :project/revision] inc)
                             (audit project-id actor
                                    (if (zero? head) :topic/created :topic/updated)
                                    [:topic topic-id] revision timestamp))
              result {:opencde/status (if (zero? head) :created :updated)
                      :opencde/topic value}
              next-state (remember next-state project-id idempotency-key request result)]
          (assoc result :opencde/state next-state))))))

(defn get-topic [state project-id actor topic-guid]
  (require-authorized! state project-id actor :topic/read)
  (get-in state [:opencde/projects project-id :project/topics
                 (string/lower (str topic-guid))]))

(defn list-topics [state project-id actor]
  (require-authorized! state project-id actor :topic/read)
  (->> (get-in state [:opencde/projects project-id :project/topics]) vals
       (sort-by #(get-in % [:topic/value :bcf.topic/guid])) vec))

(defn audit-since [state project-id actor sequence]
  (require-authorized! state project-id actor :audit/read)
  (when-not (and (integer? sequence) (<= 0 sequence (count (:opencde/audit state))))
    (throw (ex-info "OpenCDE audit cursor is out of range" {:sequence sequence})))
  (->> (:opencde/audit state)
       (filter #(and (= project-id (:audit/project-id %))
                     (> (:audit/sequence %) sequence))) vec))
