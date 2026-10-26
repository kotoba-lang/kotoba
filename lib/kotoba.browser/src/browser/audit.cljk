(ns browser.audit
  "Datom-shaped audit log for browser/session effects.")

(defn empty-log
  []
  {:audit/next-id 1
   :audit/datoms []})

(defn- next-event-id
  [audit]
  [(str "browser.audit/e" (:audit/next-id audit))
   (update audit :audit/next-id inc)])

(defn event-datoms
  [eid event]
  (let [base [[:db/add eid :audit/event (:event event)]]]
    (reduce-kv (fn [datoms k v]
                 (if (or (= k :event) (nil? v))
                   datoms
                   (conj datoms [:db/add eid k v])))
               base
               event)))

(defn append-event
  [audit event]
  (let [[eid audit] (next-event-id (or audit (empty-log)))
        datoms (event-datoms eid event)]
    (-> audit
        (update :audit/datoms into datoms)
        (assoc :audit/last-event-id eid))))

(defn append-events
  [audit events]
  (reduce append-event (or audit (empty-log)) events))

(defn events
  [audit]
  (->> (:audit/datoms audit)
       ;; `append-event` always writes one event's datoms as a contiguous run
       ;; (see `append-event`/`append-events`), so grouping consecutive runs
       ;; with `partition-by` recovers each event while preserving the
       ;; original append order. A `group-by` here would bucket by eid into
       ;; a plain hash-map, whose iteration order is hash-based rather than
       ;; chronological -- silently scrambling event order for any consumer
       ;; (e.g. `browser.browser-use/debug-state`'s `:audit-events-tail`)
       ;; that relies on `events` being oldest-first.
       (partition-by second)
       (mapv (fn [datoms]
               (reduce (fn [m [_ _ attr v]]
                         (assoc m attr v))
                       {:audit/id (second (first datoms))}
                       datoms)))))

(defn replay-summary
  [audit]
  (reduce (fn [summary event]
            (update summary (:audit/event event) (fnil inc 0)))
          {}
          (events audit)))

(defn page-commit-event
  [{:keys [url op-count profile-id]}]
  {:event :page/commit
   :url url
   :op-count op-count
   :profile/id profile-id})

(defn navigation-error-event
  [{:keys [url status error profile-id]}]
  {:event :navigation/error
   :url url
   :status status
   :error error
   :profile/id profile-id})

(defn navigation-event
  [{:keys [event url profile-id]}]
  {:event event
   :url url
   :profile/id profile-id})

(defn surface-commit-event
  [{:keys [surface-id op-count profile-id]}]
  {:event :surface/commit
   :surface/id surface-id
   :op-count op-count
   :profile/id profile-id})

(defn input-event
  [{:keys [event-type action-count profile-id]}]
  {:event :input/reduce
   :input/event-type event-type
   :action-count action-count
   :profile/id profile-id})

(defn permission-event
  [decision]
  (assoc decision :event :permission/decision))

(defn storage-event
  [{:keys [op key profile-id origin]}]
  {:event op
   :storage/key key
   :profile/id profile-id
   :origin origin})

(defn compat-event
  [{:keys [capability origin profile-id engine request-ok error]}]
  {:event :compat/request
   :capability capability
   :origin origin
   :profile/id profile-id
   :engine engine
   :request/ok? request-ok
   :error error})

(defn quickjs-event
  [{:keys [call url specifier request-count result error profile-id]}]
  {:event :quickjs/call
   :quickjs/call call
   :url url
   :specifier specifier
   :request-count request-count
   :result result
   :error error
   :profile/id profile-id})
