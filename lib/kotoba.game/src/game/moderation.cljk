(ns game.moderation
  "Portable trust-and-safety workflow for social games.

  Hosts authenticate actors, persist state, encrypt restricted evidence and
  provide clocks. Reducers here own the cross-game invariants for reports,
  cases, sanctions, appeals and append-only audit events.")

(def contract-version 1)
(def target-types #{:player :chat-message :asset :game :fork :guild})
(def report-categories #{:spam :harassment :hate :sexual :violence :self-harm
                         :cheating :fraud :impersonation :privacy :copyright :other})
(def case-statuses #{:open :investigating :resolved :dismissed})
(def case-outcomes #{:no-action :warning :content-remove :mute :restrict :suspend :ban})
(def sanction-kinds #{:warning :content-remove :mute :restrict :suspend :ban})
(def capabilities #{:chat :publish :match :social :store :login})
(def appeal-statuses #{:pending :upheld :reduced :revoked})

(defn moderation-state []
  {:moderation/version contract-version :reports {} :cases {} :sanctions {}
   :appeals {} :audit []})

(defn- bounded? [value n] (and (string? value) (seq value) (<= (count value) n)))
(defn- audit [state id actor action target at data]
  (if (or (nil? id) (some #(= id (:audit/id %)) (:audit state))) state
    (update state :audit conj #:audit{:id id :actor actor :action action
                                      :target target :at at :data data})))

(defn file-report
  "File an immutable report and open its case atomically. Report ID is the
  retry/idempotency key. Evidence is references/metadata, never raw secret data."
  [state {:report/keys [id reporter subject target-type target-id category summary
                        evidence created-at] :as report}]
  (cond
    (or (nil? id) (nil? reporter) (nil? subject)
        (not (contains? target-types target-type)) (not (bounded? target-id 256))
        (not (contains? report-categories category)) (not (bounded? summary 500))
        (not (vector? evidence)) (> (count evidence) 20) (not (integer? created-at)))
    [:error :invalid-report state]
    (contains? (:reports state) id) [:duplicate id state]
    :else
    (let [case-id (str "case:" id)
          case #:case{:id case-id :subject subject :target-type target-type
                      :target-id target-id :category category :status :open
                      :reports [id] :evidence evidence :assignee nil
                      :created-at created-at :updated-at created-at}
          next (-> state (assoc-in [:reports id] report) (assoc-in [:cases case-id] case)
                   (audit (str "audit:" id) reporter :report-filed case-id created-at
                          {:category category :target-type target-type}))]
      [:ok case-id next])))

(defn attach-report
  "Attach a distinct report to an existing compatible case. Hosts can use this
  after dedupe/cluster analysis; reporter identity remains in the report record."
  [state case-id {:report/keys [id subject target-type target-id created-at] :as report}]
  (let [case (get-in state [:cases case-id])]
    (cond
      (nil? case) [:error :case-not-found state]
      (contains? (:reports state) id) [:duplicate case-id state]
      (or (not= subject (:case/subject case)) (not= target-type (:case/target-type case))
          (not= target-id (:case/target-id case))) [:error :case-mismatch state]
      :else [:ok case-id (-> state (assoc-in [:reports id] report)
                             (update-in [:cases case-id :case/reports] conj id)
                             (assoc-in [:cases case-id :case/updated-at] created-at)
                             (audit (str "audit:" id) (:report/reporter report)
                                    :report-attached case-id created-at {}))])))

(defn assign-case [state case-id moderator at audit-id]
  (let [case (get-in state [:cases case-id])]
    (cond
      (nil? case) [:error :case-not-found state]
      (contains? #{:resolved :dismissed} (:case/status case)) [:error :case-closed state]
      (or (nil? moderator) (not (integer? at))) [:error :invalid-assignment state]
      :else [:ok (-> state
                     (assoc-in [:cases case-id :case/assignee] moderator)
                     (assoc-in [:cases case-id :case/status] :investigating)
                     (assoc-in [:cases case-id :case/updated-at] at)
                     (audit audit-id moderator :case-assigned case-id at {}))])))

(defn add-evidence [state case-id moderator evidence-ref at audit-id]
  (let [case (get-in state [:cases case-id])]
    (cond
      (nil? case) [:error :case-not-found state]
      (contains? #{:resolved :dismissed} (:case/status case)) [:error :case-closed state]
      (or (not (map? evidence-ref)) (>= (count (:case/evidence case)) 100))
      [:error :invalid-evidence state]
      :else [:ok (-> state (update-in [:cases case-id :case/evidence] conj evidence-ref)
                     (assoc-in [:cases case-id :case/updated-at] at)
                     (audit audit-id moderator :evidence-added case-id at
                            {:kind (:kind evidence-ref)}))])))

(defn valid-sanction? [{:sanction/keys [id subject kind capabilities starts-at ends-at]}]
  (and id subject (contains? sanction-kinds kind) (set? capabilities)
       (every? #(contains? game.moderation/capabilities %) capabilities)
       (integer? starts-at) (or (nil? ends-at)
                                (and (integer? ends-at) (> ends-at starts-at)))
       (or (= :warning kind) (seq capabilities))))

(defn resolve-case
  "Close a case. A punitive outcome must carry a valid sanction whose subject
  matches the case; :no-action dismisses without one."
  [state case-id moderator outcome sanction rationale at audit-id]
  (let [case (get-in state [:cases case-id])]
    (cond
      (nil? case) [:error :case-not-found state]
      (contains? #{:resolved :dismissed} (:case/status case)) [:duplicate state]
      (not (contains? case-outcomes outcome)) [:error :invalid-outcome state]
      (not (bounded? rationale 1000)) [:error :invalid-rationale state]
      (and (not= outcome :no-action)
           (or (not (valid-sanction? sanction))
               (not= (:case/subject case) (:sanction/subject sanction))
               (not= outcome (:sanction/kind sanction)))) [:error :invalid-sanction state]
      :else
      (let [status (if (= outcome :no-action) :dismissed :resolved)
            next (-> state
                     (update-in [:cases case-id] merge
                                #:case{:status status :outcome outcome :rationale rationale
                                       :resolved-by moderator :resolved-at at :updated-at at})
                     (audit audit-id moderator :case-resolved case-id at {:outcome outcome}))
            next (if sanction (assoc-in next [:sanctions (:sanction/id sanction)]
                                        (assoc sanction :sanction/case-id case-id
                                                        :sanction/revoked-at nil)) next)]
        [:ok next]))))

(defn sanction-active? [sanction now]
  (and (nil? (:sanction/revoked-at sanction))
       (<= (:sanction/starts-at sanction) now)
       (or (nil? (:sanction/ends-at sanction)) (> (:sanction/ends-at sanction) now))))

(defn denied-capabilities [state subject now]
  (->> (:sanctions state) vals
       (filter #(and (= subject (:sanction/subject %)) (sanction-active? % now)))
       (mapcat :sanction/capabilities) set))

(defn allowed? [state subject capability now]
  (and (contains? capabilities capability)
       (not (contains? (denied-capabilities state subject now) capability))))

(defn file-appeal
  [state {:appeal/keys [id sanction-id appellant statement created-at] :as appeal}]
  (let [sanction (get-in state [:sanctions sanction-id])]
    (cond
      (or (nil? sanction) (not= appellant (:sanction/subject sanction)))
      [:error :not-sanction-subject state]
      (or (not (bounded? statement 2000)) (not (integer? created-at)))
      [:error :invalid-appeal state]
      (contains? (:appeals state) id) [:duplicate state]
      (some #(and (= sanction-id (:appeal/sanction-id %))
                  (= :pending (:appeal/status %))) (vals (:appeals state)))
      [:error :appeal-already-pending state]
      :else [:ok (-> state (assoc-in [:appeals id] (assoc appeal :appeal/status :pending))
                     (audit (str "audit:" id) appellant :appeal-filed id created-at
                            {:sanction-id sanction-id}))])))

(defn review-appeal
  [state appeal-id reviewer decision rationale at audit-id replacement-ends-at]
  (let [appeal (get-in state [:appeals appeal-id])
        sanction-id (:appeal/sanction-id appeal)]
    (cond
      (nil? appeal) [:error :appeal-not-found state]
      (not= :pending (:appeal/status appeal)) [:duplicate state]
      (not (contains? #{:upheld :reduced :revoked} decision)) [:error :invalid-decision state]
      (not (bounded? rationale 1000)) [:error :invalid-rationale state]
      (and (= decision :reduced)
           (or (not (integer? replacement-ends-at)) (<= replacement-ends-at at)))
      [:error :invalid-reduction state]
      :else
      (let [next (-> state (update-in [:appeals appeal-id] merge
                                     #:appeal{:status decision :reviewer reviewer
                                              :rationale rationale :reviewed-at at})
                     (audit audit-id reviewer :appeal-reviewed appeal-id at
                            {:decision decision}))
            next (case decision
                   :revoked (assoc-in next [:sanctions sanction-id :sanction/revoked-at] at)
                   :reduced (assoc-in next [:sanctions sanction-id :sanction/ends-at]
                                      replacement-ends-at)
                   next)]
        [:ok next]))))
