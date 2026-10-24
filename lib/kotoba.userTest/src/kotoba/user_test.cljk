(ns kotoba.user-test
  "Portable contracts for evidence-driven user testing.

  This namespace contains no browser, model, filesystem, clock, issue tracker or
  business implementation. Hosts provide those effects. The separation lets the
  same study be executed by a human participant, a synthetic participant, or a
  deterministic browser recipe and compared without changing its success rubric.")

(def evidence-kinds
  #{:action-trace :accessibility-tree :console :network :screenshot :video
    :participant-note :moderator-note})

(def participant-kinds #{:human :synthetic :recipe})

(defn from-wire
  "Convert JSON-shaped data into the EDN contract. JSON has neither keywords nor
  sets, so MCP hosts must call this rather than merely keywordizing map keys."
  [value]
  (letfn [(convert [parent-key v]
            (cond
              (map? v)
              (into {}
                    (map (fn [[k child]]
                           (let [k (if (keyword? k) k (keyword k))]
                             [k (convert k child)])))
                    v)

              (= parent-key :task/success)
              (set (map #(if (keyword? %) % (keyword %)) v))

              (= parent-key :user-test/evidence)
              (mapv #(if (keyword? %) % (keyword %)) v)

              (and (= parent-key :run/participant-kind) (string? v))
              (keyword v)

              (vector? v) (mapv #(convert nil %) v)
              :else v))]
    (convert nil value)))

(defn study-errors
  "Return deterministic validation errors for a study EDN value. Empty means
  valid. Business-specific persona content may be referenced by opaque id; it
  does not have to be copied into a public study."
  [study]
  (let [tasks (:user-test/tasks study)]
    (cond-> []
      (not (map? study))
      (conj {:path [] :rule :map-required})

      (not (string? (:user-test/id study)))
      (conj {:path [:user-test/id] :rule :string-required})

      (not (string? (:user-test/project study)))
      (conj {:path [:user-test/project] :rule :string-required})

      (not (string? (:user-test/persona study)))
      (conj {:path [:user-test/persona] :rule :opaque-persona-ref-required})

      (not (string? (:user-test/revision study)))
      (conj {:path [:user-test/revision] :rule :immutable-revision-required})

      (not (and (vector? tasks) (seq tasks)))
      (conj {:path [:user-test/tasks] :rule :non-empty-vector-required})

      (and (vector? tasks)
           (not-every? #(and (string? (:task/id %))
                             (string? (:task/goal %))
                             (set? (:task/success %))
                             (seq (:task/success %)))
                       tasks))
      (conj {:path [:user-test/tasks]
             :rule :task-requires-id-goal-and-success-set})

      (and (contains? study :user-test/evidence)
           (not (every? evidence-kinds (:user-test/evidence study))))
      (conj {:path [:user-test/evidence] :rule :unknown-evidence-kind}))))

(defn valid-study? [study] (empty? (study-errors study)))

(defn execution-plan
  "Turn a valid study into executor-neutral tasks. Persona remains an opaque
  reference so an executor may resolve it from a private local store."
  [study]
  (when-let [errors (seq (study-errors study))]
    (throw (ex-info "invalid user-test study"
                    {:type :user-test/invalid-study :errors errors})))
  {:plan/study (:user-test/id study)
   :plan/project (:user-test/project study)
   :plan/persona (:user-test/persona study)
   :plan/revision (:user-test/revision study)
   :plan/tasks
   (mapv (fn [task]
           {:task/id (:task/id task)
            :task/goal (:task/goal task)
            :task/start-url (:task/start-url task)
            :task/success (:task/success task)
            :task/max-seconds (or (:task/max-seconds task) 120)})
         (:user-test/tasks study))
   :plan/evidence (or (:user-test/evidence study)
                      [:action-trace :accessibility-tree :screenshot])})

(defn run-errors
  "Validate an immutable observation record. The run reports facts; it does not
  contain an LLM's prose assertion that a task succeeded."
  [study run]
  (let [task-ids (set (map :task/id (:user-test/tasks study)))
        outcomes (:run/outcomes run)]
    (cond-> []
      (not (valid-study? study))
      (conj {:path [:run/study] :rule :invalid-study})

      (not= (:user-test/id study) (:run/study run))
      (conj {:path [:run/study] :rule :study-mismatch})

      (not (contains? participant-kinds (:run/participant-kind run)))
      (conj {:path [:run/participant-kind] :rule :unknown-participant-kind})

      (not (string? (:run/participant run)))
      (conj {:path [:run/participant] :rule :participant-ref-required})

      (not= (:user-test/revision study) (:run/revision run))
      (conj {:path [:run/revision] :rule :revision-mismatch})

      (not (vector? outcomes))
      (conj {:path [:run/outcomes] :rule :vector-required})

      (and (vector? outcomes)
           (not= task-ids (set (map :task/id outcomes))))
      (conj {:path [:run/outcomes] :rule :exact-task-coverage-required})

      (and (vector? outcomes)
           (not-every? #(and (boolean? (:outcome/succeeded? %))
                             (number? (:outcome/elapsed-ms %))
                             (not (neg? (:outcome/elapsed-ms %)))
                             (nat-int? (or (:outcome/actions %) 0))
                             (nat-int? (or (:outcome/dead-ends %) 0))
                             (nat-int? (or (:outcome/recoveries %) 0)))
                       outcomes))
      (conj {:path [:run/outcomes] :rule :invalid-outcome-metrics})

      (not (map? (:run/evidence run)))
      (conj {:path [:run/evidence] :rule :evidence-map-required}))))

(defn valid-run? [study run] (empty? (run-errors study run)))

(defn- safe-div [n d] (if (pos? d) (/ (double n) d) 0.0))

(defn evaluate
  "Evaluate observed outcomes with transparent arithmetic. A host may add an
  independent qualitative judge, but cannot replace these facts with it."
  [study run]
  (when-let [errors (seq (run-errors study run))]
    (throw (ex-info "invalid user-test run"
                    {:type :user-test/invalid-run :errors errors})))
  (let [outcomes (:run/outcomes run)
        total (count outcomes)
        succeeded (count (filter :outcome/succeeded? outcomes))
        elapsed (reduce + 0 (map :outcome/elapsed-ms outcomes))
        actions (reduce + 0 (map #(or (:outcome/actions %) 0) outcomes))
        dead-ends (reduce + 0 (map #(or (:outcome/dead-ends %) 0) outcomes))
        recoveries (reduce + 0 (map #(or (:outcome/recoveries %) 0) outcomes))
        accessibility (reduce + 0 (map #(or (:outcome/a11y-violations %) 0)
                                           outcomes))]
    {:evaluation/study (:user-test/id study)
     :evaluation/run (:run/id run)
     :evaluation/project (:user-test/project study)
     :evaluation/revision (:run/revision run)
     :evaluation/participant-kind (:run/participant-kind run)
     :metric/task-success-rate (safe-div succeeded total)
     :metric/mean-elapsed-ms (safe-div elapsed total)
     :metric/actions actions
     :metric/dead-ends dead-ends
     :metric/recoveries recoveries
     :metric/a11y-violations accessibility
     :evaluation/pass? (and (= succeeded total)
                            (zero? dead-ends)
                            (zero? accessibility))
     :evaluation/failed-tasks
     (mapv :task/id (remove :outcome/succeeded? outcomes))}))

(defn findings
  "Produce issue-shaped, deduplicatable findings from deterministic scores."
  [evaluation]
  (cond-> []
    (< (:metric/task-success-rate evaluation) 1.0)
    (conj {:finding/key [(:evaluation/study evaluation) :task-failure]
           :finding/kind :task-failure
           :finding/severity :blocking
           :finding/tasks (:evaluation/failed-tasks evaluation)})

    (pos? (:metric/dead-ends evaluation))
    (conj {:finding/key [(:evaluation/study evaluation) :dead-end]
           :finding/kind :dead-end
           :finding/severity :high
           :finding/count (:metric/dead-ends evaluation)})

    (pos? (:metric/a11y-violations evaluation))
    (conj {:finding/key [(:evaluation/study evaluation) :accessibility]
           :finding/kind :accessibility
           :finding/severity :high
           :finding/count (:metric/a11y-violations evaluation)})))

(defn project-summary
  "Aggregate evaluations for a business/project projection. Synthetic results
  are reported separately from human evidence; averaging them together would
  make synthetic confidence look like market validation."
  [project evaluations]
  (let [rows (filter #(= project (:evaluation/project %)) evaluations)
        by-kind (group-by :evaluation/participant-kind rows)]
    {:project/id project
     :user-test/runs (count rows)
     :user-test/by-participant
     (into (sorted-map)
           (for [[kind rs] by-kind]
             [kind {:runs (count rs)
                    :pass-rate (safe-div (count (filter :evaluation/pass? rs))
                                         (count rs))
                    :task-success-rate
                    (safe-div (reduce + 0 (map :metric/task-success-rate rs))
                              (count rs))}]))
     :user-test/open-findings (vec (mapcat findings rows))
     :user-test/human-calibrated? (boolean (seq (get by-kind :human)))}))

(def private-keys
  "Fields that must not leave a participant-controlled/private evidence store."
  #{:persona/name :persona/email :persona/notes :run/transcript
    :run/raw-events :evidence/content :evidence/path :evidence/url})

(defn public-projection
  "Recursively remove direct participant content. This is a publication helper,
  not encryption: private artifacts still belong in a private/local store."
  [value]
  (cond
    (map? value) (into {} (keep (fn [[k v]]
                                  (when-not (contains? private-keys k)
                                    [k (public-projection v)]))) value)
    (vector? value) (mapv public-projection value)
    (set? value) (set (map public-projection value))
    (sequential? value) (doall (map public-projection value))
    :else value))
