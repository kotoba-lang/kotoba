(ns fleet.eval
  "Did the agent actually do the task? — decided from the patch, not by asking
  a model.

  Everything the fleet knew so far was that ONE ~10-line task passes. That is
  not a capability measurement, and the obvious way to get one — have an LLM
  judge the output — measures the judge. So a benchmark task carries an
  `:expect` map of mechanical conditions over the diff, and this namespace is
  pure: same patch, same verdict, every time, no network and no model.

  A run is scored on two independent axes, because they fail differently:
  - **accepted** — the fleet's own gate took it (patch applies to the pin,
    tests green on the node, no protected path). This is what the fleet
    already enforces.
  - **meets-spec** — the patch did what the TASK asked. A patch can be
    accepted and still be wrong work: deleting the requirement and leaving the
    suite green passes the gate and fails here."
  (:require [kotoba.lang.text :as str]))

(defn diff-files [diff]
  (->> (str/split-lines (or diff ""))
       (keep #(second (re-find #"^diff --git a/(\S+) b/" %)))
       distinct vec))

(defn added-lines
  "Only the ADDED side of the patch. Checking the whole diff would let a task
  pass because the string it wanted appears in a line the agent DELETED."
  [diff]
  (->> (str/split-lines (or diff ""))
       (filter #(and (str/starts-with? % "+") (not (str/starts-with? % "+++"))))
       (map #(subs % 1))
       (str/join "\n")))

(defn check
  "Score one run against a task's `:expect`. Returns
  {:meets-spec bool :failures [reason …]}.

  expect keys:
    :files-subset-of   every touched file must be in this set
    :must-touch        every one of these files must be touched
    :max-files         at most this many files
    :must-add          regex strings that must appear in the ADDED lines
    :must-not-add      regex strings that must NOT appear in the added lines"
  [diff {:keys [files-subset-of must-touch max-files must-add must-not-add]}]
  (let [files (diff-files diff)
        added (added-lines diff)
        fails
        (cond-> []
          (str/blank? diff) (conj "no patch")

          (and files-subset-of (some #(not (contains? (set files-subset-of) %)) files))
          (conj (str "touched files outside the task: "
                     (vec (remove (set files-subset-of) files))))

          (and must-touch (some #(not (contains? (set files) %)) must-touch))
          (conj (str "did not touch: " (vec (remove (set files) must-touch))))

          (and max-files (> (count files) max-files))
          (conj (str (count files) " files changed, at most " max-files " expected"))

          true
          (into (keep (fn [re] (when-not (re-find (re-pattern re) added)
                                 (str "missing from the patch: " re)))
                      must-add))

          true
          (into (keep (fn [re] (when (re-find (re-pattern re) added)
                                 (str "patch adds something it should not: " re)))
                      must-not-add)))]
    {:meets-spec (empty? fails) :failures fails}))

(defn score-run
  "One run's row: what the fleet decided, what the task asked, and — when they
  disagree — which one failed."
  [{:keys [task rep payload verdict expect]}]
  (let [{:keys [meets-spec failures]} (check (:diff payload) expect)
        accepted (= :accepted verdict)]
    {:task task :rep rep
     :accepted accepted
     :meets-spec meets-spec
     :pass (and accepted meets-spec)
     :turns (:turns payload)
     :tool-calls (:tool-calls payload)
     :tests-exit (get-in payload [:tests :final-exit])
     :model-errors (:model-errors payload)
     :files (diff-files (:diff payload))
     :diff-bytes (count (:diff payload))
     :wall-ms (:wall-ms payload)
     :failures (cond-> failures
                 (not accepted) (conj (str "gate did not accept (verdict "
                                           (pr-str verdict) ")")))}))

(defn summarize
  "Per-task pass rate plus the totals. Deliberately reports pass rate over
  ATTEMPTS, not best-of-N: a fleet runs the agent once per work-unit, so a
  task that succeeds one time in three is a task that fails two thirds of the
  time."
  [rows]
  (let [by-task (group-by :task rows)]
    {:tasks (into {} (map (fn [[t rs]]
                            [t {:attempts (count rs)
                                :passed (count (filter :pass rs))
                                :accepted (count (filter :accepted rs))
                                :met-spec (count (filter :meets-spec rs))
                                :median-turns (let [ts (sort (keep :turns rs))]
                                                (when (seq ts) (nth ts (quot (count ts) 2))))}])
                          by-task))
     :total {:attempts (count rows)
             :passed (count (filter :pass rows))
             :accepted (count (filter :accepted rows))
             :met-spec (count (filter :meets-spec rows))}}))
