(ns simulated-user.eval)

(def environments #{:survey :chatbot :web :app})
(def allowed-purposes #{:product-evaluation :research})
(def prohibited-purposes
  #{:persuasion :political-targeting :credit-decision :employment-decision
    :insurance-decision :healthcare-decision :eligibility-decision})
(def minimum-aggregate-size 5)

(defn- fail [message data]
  (throw (ex-info message data)))

(defn validate-task
  [{:keys [task/id environment purpose decision-impact prompt] :as task}]
  (when-not (keyword? id)
    (fail "Task id must be a keyword" {:task task}))
  (when-not (contains? environments environment)
    (fail "Unsupported evaluation environment"
          {:environment environment :allowed environments}))
  (when (contains? prohibited-purposes purpose)
    (fail "The requested purpose is structurally prohibited" {:purpose purpose}))
  (when-not (contains? allowed-purposes purpose)
    (fail "Task purpose must be product-evaluation or research" {:purpose purpose}))
  (when-not (= :none decision-impact)
    (fail "Simulated-user output cannot make decisions about people"
          {:decision-impact decision-impact}))
  (when-not (and (string? prompt) (seq prompt))
    (fail "Task prompt must be a non-empty string" {:prompt prompt}))
  task)

(defn run-trial
  "Run one host-owned interaction. The library never calls a model or network."
  [interact task persona context]
  (validate-task task)
  (when-not (fn? interact)
    (fail "An injected interact function is required" {}))
  (let [response (interact {:task task :persona persona :context context})
        score (:score response)]
    (when-not (and (number? score) (<= 0 score 1))
      (fail "Interaction response score must be between 0 and 1"
            {:response response}))
    {:trial/task-id (:task/id task)
     :trial/environment (:environment task)
     :trial/persona-id (:simulated-user/id persona)
     :trial/score score
     :trial/response (dissoc response :score)}))

(defn run-cohort
  [interact task cohort context]
  (mapv #(run-trial interact task % context) cohort))

(defn aggregate
  "Return only cohort-level metrics. Small cohorts are rejected."
  [trials]
  (let [n (count trials)]
    (when (< n minimum-aggregate-size)
      (fail "At least five trials are required for an aggregate" {:count n}))
    (let [scores (map :trial/score trials)]
      {:aggregate/count n
       :aggregate/mean-score (/ (reduce + scores) n)
       :aggregate/min-score (reduce min scores)
       :aggregate/max-score (reduce max scores)
       :aggregate/environments (frequencies (map :trial/environment trials))})))

(defn evaluate
  "Evaluate a cohort and expose the aggregate as the formal result."
  [interact task cohort context]
  (aggregate (run-cohort interact task cohort context)))
