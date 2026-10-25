(ns bim.worksharing
  "Element leases, role authorization, and optimistic transaction conflict
  detection for BIM worksharing."
  (:require [bim.editor :as editor]))

(def schema-version 1)
(def default-capabilities
  {:viewer #{:read} :reviewer #{:read :comment :review}
   :author #{:read :comment :edit} :manager #{:read :comment :review :edit :admin}})

(defn workspace [document memberships]
  {:worksharing/schema-version schema-version
   :worksharing/editor (editor/editor-state document)
   :worksharing/memberships memberships :worksharing/leases {}
   :worksharing/presence {}
   :worksharing/revision 0 :worksharing/history []})

(defn- capability? [state actor capability]
  (contains? (get default-capabilities (get-in state [:worksharing/memberships actor]) #{})
             capability))

(defn prune-expired-leases
  "Remove leases whose expiry is not later than `now`."
  [state now]
  (update state :worksharing/leases
          (fn [leases]
            (into {} (filter (fn [[_ lease]] (> (:lease/expires-at lease) now)) leases)))))

(defn checkout
  "Acquire element leases atomically. Expired leases may be reclaimed."
  [state actor element-ids now lease-duration]
  (when-not (capability? state actor :edit)
    (throw (ex-info "actor is not authorized to edit" {:actor actor})))
  (when-not (and (seq element-ids) (number? lease-duration) (pos? lease-duration))
    (throw (ex-info "checkout requires elements and a positive lease duration"
                    {:element-ids element-ids :lease-duration lease-duration})))
  (let [state (prune-expired-leases state now)
        conflicts (keep (fn [element-id]
                          (let [lease (get-in state [:worksharing/leases element-id])]
                            (when (and lease (> (:lease/expires-at lease) now)
                                       (not= actor (:lease/actor lease)))
                              {:element-id element-id :held-by (:lease/actor lease)
                               :expires-at (:lease/expires-at lease)})))
                        element-ids)]
    (when (seq conflicts)
      (throw (ex-info "elements are checked out by another actor"
                      {:actor actor :conflicts (vec conflicts)})))
    (reduce (fn [result element-id]
              (assoc-in result [:worksharing/leases element-id]
                        {:lease/actor actor :lease/acquired-at now
                         :lease/expires-at (+ now lease-duration)}))
            state element-ids)))

(defn renew-leases
  "Atomically renew active leases owned by an editor. A partially invalid
  renewal is rejected without extending any lease."
  [state actor element-ids now lease-duration]
  (when-not (and (seq element-ids) (number? lease-duration) (pos? lease-duration))
    (throw (ex-info "lease renewal requires elements and a positive duration"
                    {:element-ids element-ids :lease-duration lease-duration})))
  (let [invalid
        (vec (filter (fn [element-id]
                       (let [lease (get-in state [:worksharing/leases element-id])]
                         (not (and (= actor (:lease/actor lease))
                                   (> (:lease/expires-at lease 0) now)))))
                     element-ids))]
    (when (seq invalid)
      (throw (ex-info "lease renewal requires active owned leases"
                      {:actor actor :element-ids invalid})))
    (reduce (fn [result element-id]
              (-> result
                  (assoc-in [:worksharing/leases element-id :lease/renewed-at] now)
                  (assoc-in [:worksharing/leases element-id :lease/expires-at]
                            (+ now lease-duration))))
            state element-ids)))

(defn relinquish [state actor element-ids]
  (reduce (fn [result element-id]
            (if (= actor (get-in result [:worksharing/leases element-id :lease/actor]))
              (update result :worksharing/leases dissoc element-id)
              result))
          state element-ids))

(defn heartbeat
  "Publish ephemeral editor presence with a monotonic client sequence."
  [state actor now {:keys [sequence view-id cursor selection] :as presence}]
  (when-not (capability? state actor :read)
    (throw (ex-info "actor is not authorized to publish presence" {:actor actor})))
  (let [previous (get-in state [:worksharing/presence actor])]
    (when-not (and (integer? sequence) (<= 0 sequence)
                   (> sequence (:presence/sequence previous -1)))
      (throw (ex-info "presence sequence must advance monotonically"
                      {:actor actor :sequence sequence
                       :previous (:presence/sequence previous)})))
    (assoc-in state [:worksharing/presence actor]
              {:presence/actor actor :presence/sequence sequence
               :presence/updated-at now :presence/view-id view-id
               :presence/cursor cursor :presence/selection (set selection)
               :presence/metadata (dissoc presence :sequence :view-id :cursor :selection)})))

(defn active-presence
  "Return peers updated within the timeout, excluding an optional local actor."
  ([state now timeout] (active-presence state now timeout nil))
  ([state now timeout local-actor]
   (into {}
         (filter (fn [[actor presence]]
                   (and (not= actor local-actor)
                        (> (+ (:presence/updated-at presence) timeout) now))))
         (:worksharing/presence state))))

(defn- path-overlap? [left right]
  (let [common (min (count left) (count right))]
    (= (subvec (vec left) 0 common) (subvec (vec right) 0 common))))

(defn submit
  "Authorize and apply an editor transaction at a base revision. Concurrent
  transactions merge when their paths are disjoint; overlapping paths return
  a semantic conflict without mutating the workspace."
  [state actor base-revision now transaction]
  (when-not (capability? state actor :edit)
    (throw (ex-info "actor is not authorized to edit" {:actor actor})))
  (when-not (:id transaction)
    (throw (ex-info "worksharing transaction requires an id" {:transaction transaction})))
  (let [existing (first (filter #(= (:transaction/id %) (:id transaction))
                                (:worksharing/history state)))]
    (when (and existing
               (not (and (= actor (:actor existing))
                         (= transaction (:transaction existing)))))
      (throw (ex-info "transaction id conflicts with prior submission"
                      {:transaction/id (:id transaction) :revision (:revision existing)})))
    (if existing
      {:worksharing/status :deduplicated :worksharing/workspace state
       :worksharing/revision (:revision existing)}
      (do
        (when (> base-revision (:worksharing/revision state))
          (throw (ex-info "transaction base revision is ahead of workspace"
                          {:base-revision base-revision
                           :workspace-revision (:worksharing/revision state)})))
        (let [element-ids (set (:transaction/element-ids transaction))
          invalid-leases
          (keep (fn [element-id]
                  (let [lease (get-in state [:worksharing/leases element-id])]
                    (when-not (and (= actor (:lease/actor lease))
                                   (> (:lease/expires-at lease 0) now))
                      element-id)))
                element-ids)
          _ (when (seq invalid-leases)
              (throw (ex-info "transaction requires active element leases"
                              {:actor actor :element-ids (vec invalid-leases)})))
          incoming-paths (mapv :path (:operations transaction))
          concurrent (filter #(> (:revision %) base-revision) (:worksharing/history state))
          conflicts (vec
                     (for [entry concurrent
                           incoming incoming-paths existing (:paths entry)
                           :when (path-overlap? incoming existing)]
                       {:incoming-path incoming :existing-path existing
                        :revision (:revision entry) :actor (:actor entry)}))]
      (if (seq conflicts)
        {:worksharing/status :conflict :worksharing/workspace state
         :worksharing/conflicts conflicts
         :worksharing/pending {:actor actor :base-revision base-revision
                               :submitted-at now :transaction transaction}}
        (let [next-revision (inc (:worksharing/revision state))
              next-state (-> state
                             (update :worksharing/editor editor/transact transaction)
                             (assoc :worksharing/revision next-revision)
                             (update :worksharing/history conj
                                     {:revision next-revision :base-revision base-revision
                                      :actor actor :transaction/id (:id transaction)
                                      :transaction transaction
                                      :element-ids element-ids :paths incoming-paths
                                      :timestamp now}))]
          {:worksharing/status :applied :worksharing/workspace next-state
           :worksharing/revision next-revision})))))))

(defn resolve-conflict
  "Resolve every incoming conflict from `submit` and commit the result at the
  current head. A resolution is `{:path p :strategy :incoming|:current}` or
  `{:path p :strategy :value :value v}`. Non-conflicting operations are always
  retained and the chosen resolutions are recorded in revision history."
  [conflict-result actor now resolutions]
  (when-not (= :conflict (:worksharing/status conflict-result))
    (throw (ex-info "worksharing result has no conflict"
                    {:status (:worksharing/status conflict-result)})))
  (let [state (:worksharing/workspace conflict-result)
        pending (:worksharing/pending conflict-result)
        transaction (:transaction pending)
        conflict-paths (set (map (comp vec :incoming-path)
                                 (:worksharing/conflicts conflict-result)))
        resolution-by-path (into {} (map (juxt (comp vec :path) identity) resolutions))]
    (when-not (= actor (:actor pending))
      (throw (ex-info "only the pending transaction actor can resolve its conflict"
                      {:actor actor :pending-actor (:actor pending)})))
    (when-not (capability? state actor :edit)
      (throw (ex-info "actor is not authorized to edit" {:actor actor})))
    (when-not (= conflict-paths (set (keys resolution-by-path)))
      (throw (ex-info "every worksharing conflict needs exactly one resolution"
                      {:expected conflict-paths :actual (set (keys resolution-by-path))})))
    (doseq [[path resolution] resolution-by-path]
      (when-not (contains? #{:incoming :current :value} (:strategy resolution))
        (throw (ex-info "unsupported worksharing conflict resolution"
                        {:path path :strategy (:strategy resolution)}))))
    (let [element-ids (set (:transaction/element-ids transaction))
          invalid-leases
          (filterv (fn [element-id]
                     (let [lease (get-in state [:worksharing/leases element-id])]
                       (not (and (= actor (:lease/actor lease))
                                 (> (:lease/expires-at lease 0) now)))))
                   element-ids)]
      (when (seq invalid-leases)
        (throw (ex-info "conflict resolution requires active element leases"
                        {:actor actor :element-ids invalid-leases})))
      (let [operations
            (vec
             (keep (fn [operation]
                     (if-let [{:keys [strategy value]}
                              (resolution-by-path (vec (:path operation)))]
                       (case strategy
                         :incoming operation
                         :current nil
                         :value (assoc operation :op :set :value value))
                       operation))
                   (:operations transaction)))
            resolved-transaction (assoc transaction :operations operations)
            next-revision (inc (:worksharing/revision state))
            next-state
            (cond-> state
              (seq operations) (update :worksharing/editor editor/transact
                                       resolved-transaction)
              true (assoc :worksharing/revision next-revision)
              true (update :worksharing/history conj
                           {:revision next-revision
                            :base-revision (:base-revision pending)
                            :resolved-at-revision (:worksharing/revision state)
                            :actor actor :transaction/id (:id transaction)
                            :transaction resolved-transaction :element-ids element-ids
                            :paths (mapv :path operations) :timestamp now
                            :conflict/resolutions (vec resolutions)}))]
        {:worksharing/status :resolved :worksharing/workspace next-state
         :worksharing/revision next-revision
         :worksharing/resolutions (vec resolutions)}))))

(defn changes-since
  "Return an ordered replay delta after a durable workspace revision."
  [state revision]
  (when-not (and (integer? revision) (<= 0 revision (:worksharing/revision state)))
    (throw (ex-info "worksharing revision cursor is out of range"
                    {:revision revision :head (:worksharing/revision state)})))
  {:worksharing/schema-version schema-version
   :worksharing/from-revision revision
   :worksharing/to-revision (:worksharing/revision state)
   :worksharing/transactions
   (mapv #(select-keys % [:revision :base-revision :actor :transaction :timestamp])
         (filter #(> (:revision %) revision) (:worksharing/history state)))})
