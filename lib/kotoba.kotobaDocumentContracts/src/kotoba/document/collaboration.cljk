(ns kotoba.document.collaboration
  "Domain-neutral revision, branch, merge, review, issue, and sync contracts."
  (:require [kotoba.document.change :as change]))

(def schema-version 1)

(defn workspace [{:keys [id document default-branch]}]
  (let [branch (or default-branch :main)
        root {:revision/id "root" :revision/parents [] :revision/branch branch
              :revision/actor :system :revision/clock 0 :revision/message "Initial"
              :revision/events [] :revision/document document}]
    {:collab/schema-version schema-version :collab/id id
     :collab/default-branch branch :collab/revisions {"root" root}
     :collab/branches {branch "root"} :collab/issues {} :collab/reviews {}}))

(defn branch [workspace branch-id from-revision]
  (when-not (contains? (:collab/revisions workspace) from-revision)
    (throw (ex-info "branch base revision not found" {:revision from-revision})))
  (when (contains? (:collab/branches workspace) branch-id)
    (throw (ex-info "branch already exists" {:branch branch-id})))
  (assoc-in workspace [:collab/branches branch-id] from-revision))

(defn revision [workspace revision-id]
  (get-in workspace [:collab/revisions revision-id]))

(defn branch-head [workspace branch-id]
  (get-in workspace [:collab/branches branch-id]))

(defn commit
  "Optimistically commit events when `base-revision` is still the branch head."
  [workspace {:keys [id branch base-revision actor clock message events]}]
  (let [head (branch-head workspace branch)]
    (when-not head (throw (ex-info "branch not found" {:branch branch})))
    (when-not (= head base-revision)
      (throw (ex-info "stale branch revision"
                      {:branch branch :expected head :actual base-revision})))
    (when (contains? (:collab/revisions workspace) id)
      (throw (ex-info "revision already exists" {:revision id})))
    (let [document (change/replay (:revision/document (revision workspace head)) events)
          next-revision {:revision/id id :revision/parents [head] :revision/branch branch
                         :revision/actor actor :revision/clock clock :revision/message message
                         :revision/events (vec events) :revision/document document}]
      (-> workspace
          (assoc-in [:collab/revisions id] next-revision)
          (assoc-in [:collab/branches branch] id)))))

(defn- ancestor-depths [workspace revision-id]
  (loop [queue [[revision-id 0]] result {}]
    (if-let [[current depth] (first queue)]
      (if (contains? result current)
        (recur (subvec (vec queue) 1) result)
        (recur (into (subvec (vec queue) 1)
                     (map #(vector % (inc depth))
                          (:revision/parents (revision workspace current))))
               (assoc result current depth)))
      result)))

(defn common-ancestor [workspace a b]
  (let [a-depths (ancestor-depths workspace a) b-depths (ancestor-depths workspace b)
        shared (filter #(contains? b-depths %) (keys a-depths))]
    (when (seq shared)
      (apply min-key #(+ (a-depths %) (b-depths %)) shared))))

(defn- revisions-between [workspace head ancestor]
  (loop [current head result []]
    (if (= current ancestor)
      result
      (let [value (revision workspace current) parent (first (:revision/parents value))]
        (when-not value
          (throw (ex-info "revision ancestry is incomplete" {:revision current})))
        (recur parent (conj result value))))))

(defn- path-prefix? [a b]
  (and (<= (count a) (count b)) (= a (subvec (vec b) 0 (count a)))))

(defn conflicting-events [target-events source-events]
  (vec
   (for [target target-events source source-events
         :when (and (or (path-prefix? (:event/path target) (:event/path source))
                        (path-prefix? (:event/path source) (:event/path target)))
                    (not (and (= (:event/operation target) (:event/operation source))
                              (= (:event/path target) (:event/path source))
                              (= (:event/value target) (:event/value source)))))]
     {:conflict/path (if (<= (count (:event/path target)) (count (:event/path source)))
                       (:event/path target) (:event/path source))
      :conflict/target-event target :conflict/source-event source})))

(defn review [workspace {:keys [revision reviewer decision comment clock]}]
  (when-not (contains? (:collab/revisions workspace) revision)
    (throw (ex-info "review revision not found" {:revision revision})))
  (when-not (#{:approved :changes-requested :commented} decision)
    (throw (ex-info "unsupported review decision" {:decision decision})))
  (assoc-in workspace [:collab/reviews revision reviewer]
            {:review/revision revision :review/reviewer reviewer :review/decision decision
             :review/comment comment :review/clock clock}))

(defn approval-count [workspace revision-id]
  (count (filter #(= :approved (:review/decision %))
                 (vals (get-in workspace [:collab/reviews revision-id])))))

(defn merge-branches
  "Three-way merge branch heads. Returns `:conflict`, `:review-required`, or
  `:merged` plus the resulting workspace."
  [workspace {:keys [id target source actor clock message required-approvals]
              :or {required-approvals 0}}]
  (let [target-head (branch-head workspace target) source-head (branch-head workspace source)]
    (when-not (and target-head source-head)
      (throw (ex-info "merge branch not found" {:target target :source source})))
    (if (< (approval-count workspace source-head) required-approvals)
      {:merge/status :review-required :merge/source-revision source-head
       :merge/required-approvals required-approvals
       :merge/current-approvals (approval-count workspace source-head) :merge/workspace workspace}
      (let [ancestor (common-ancestor workspace target-head source-head)
            target-revisions (revisions-between workspace target-head ancestor)
            source-revisions (revisions-between workspace source-head ancestor)
            target-events (vec (mapcat :revision/events (reverse target-revisions)))
            source-events (vec (mapcat :revision/events (reverse source-revisions)))
            conflicts (conflicting-events target-events source-events)]
        (if (seq conflicts)
          {:merge/status :conflict :merge/id id :merge/target target :merge/source source
           :merge/target-revision target-head :merge/source-revision source-head
           :merge/ancestor ancestor :merge/target-events target-events
           :merge/source-events source-events
           :merge/conflicts conflicts :merge/workspace workspace}
          (let [document (change/replay (:revision/document (revision workspace ancestor))
                                        (concat target-events source-events))
                merged {:revision/id id :revision/parents [target-head source-head]
                        :revision/branch target :revision/actor actor :revision/clock clock
                        :revision/message message :revision/events (vec source-events)
                        :revision/document document}
                next-workspace (-> workspace
                                   (assoc-in [:collab/revisions id] merged)
                                   (assoc-in [:collab/branches target] id))]
            {:merge/status :merged :merge/revision id :merge/workspace next-workspace}))))))

(defn resolve-merge
  "Resolve every conflict with `{path value}` choices and create a two-parent revision."
  [merge-result {:keys [id actor clock message resolutions]}]
  (when-not (= :conflict (:merge/status merge-result))
    (throw (ex-info "merge result has no conflicts" {:status (:merge/status merge-result)})))
  (let [workspace (:merge/workspace merge-result)
        paths (set (map :conflict/path (:merge/conflicts merge-result)))
        resolution-paths (set (map (comp vec :path) resolutions))]
    (when-not (= paths resolution-paths)
      (throw (ex-info "every conflict needs exactly one resolution"
                      {:expected paths :actual resolution-paths})))
    (let [target (:merge/target merge-result)
          target-head (:merge/target-revision merge-result)
          source-head (:merge/source-revision merge-result)
          base-document (:revision/document (revision workspace target-head))
          conflicted-source-ids (set (map #(get-in % [:conflict/source-event :event/id])
                                          (:merge/conflicts merge-result)))
          retained-source-events (remove #(contains? conflicted-source-ids (:event/id %))
                                         (:merge/source-events merge-result))
          resolution-events (mapv (fn [[index {:keys [path value]}]]
                                    (change/event {:id (str id "-resolve-" index) :actor actor :clock clock
                                                   :operation :assoc :path path :value value}))
                                  (map-indexed vector resolutions))
          events (vec (concat retained-source-events resolution-events))
          document (change/replay base-document events)
          merged {:revision/id id :revision/parents [target-head source-head]
                  :revision/branch target :revision/actor actor :revision/clock clock
                  :revision/message message :revision/events events :revision/document document}
          next-workspace (-> workspace
                             (assoc-in [:collab/revisions id] merged)
                             (assoc-in [:collab/branches target] id))]
      {:merge/status :merged :merge/revision id :merge/workspace next-workspace})))

(def issue-transitions
  {:open #{:in-review :resolved :closed} :in-review #{:open :resolved}
   :resolved #{:open :closed} :closed #{:open}})

(defn create-issue [workspace {:keys [id title description author assignee element-ids clock]}]
  (when (contains? (:collab/issues workspace) id)
    (throw (ex-info "issue already exists" {:issue id})))
  (assoc-in workspace [:collab/issues id]
            {:issue/id id :issue/title title :issue/description description :issue/status :open
             :issue/author author :issue/assignee assignee :issue/element-ids (vec element-ids)
             :issue/created-clock clock :issue/history []}))

(defn transition-issue [workspace issue-id status actor clock comment]
  (let [current (get-in workspace [:collab/issues issue-id :issue/status])]
    (when-not current (throw (ex-info "issue not found" {:issue issue-id})))
    (when-not (contains? (issue-transitions current) status)
      (throw (ex-info "invalid issue transition" {:issue issue-id :from current :to status})))
    (-> workspace
        (assoc-in [:collab/issues issue-id :issue/status] status)
        (update-in [:collab/issues issue-id :issue/history] conj
                   {:issue/from current :issue/to status :issue/actor actor
                    :issue/clock clock :issue/comment comment}))))

(defn checkpoint [workspace peer-id]
  {:sync/schema-version schema-version :sync/workspace (:collab/id workspace)
   :sync/peer peer-id :sync/branches (:collab/branches workspace)
   :sync/revisions (set (keys (:collab/revisions workspace)))})

(defn changes-since [workspace checkpoint]
  {:sync/schema-version schema-version :sync/workspace (:collab/id workspace)
   :sync/branches (:collab/branches workspace)
   :sync/revisions (into {} (remove (fn [[id _]] (contains? (:sync/revisions checkpoint) id))
                                    (:collab/revisions workspace)))
   :sync/issues (:collab/issues workspace)
   :sync/reviews (:collab/reviews workspace)})
