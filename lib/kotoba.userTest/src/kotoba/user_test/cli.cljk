(ns kotoba.user-test.cli
  (:require [kotoba.lang.fmt :as fmt]
            [kotoba.user-test :as user-test]
            [kotoba.user-test.io :as user-io]))

(defn- option [args flag]
  (second (drop-while #(not= flag %) args)))

(defn execute [args]
  (let [[scope command & options] args
        study-path (option options "--study")
        run-path (option options "--run")
        study (when study-path (user-io/read-edn study-path))]
    (case [scope command]
      ["study" "validate"]
      {:ok? (user-test/valid-study? study)
       :errors (user-test/study-errors study)}

      ["study" "plan"]
      (user-test/execution-plan study)

      ["run" "evaluate"]
      (let [run (user-io/read-edn run-path)
            evaluation (user-test/evaluate study run)]
        {:evaluation evaluation
         :findings (user-test/findings evaluation)})

      ["project" "summarize"]
      (let [project (option options "--project")
            evaluations (user-io/read-edn (option options "--evaluations"))]
        (user-test/project-summary project evaluations))

      ["publication" "redact"]
      (user-test/public-projection
       (user-io/read-edn (option options "--input")))

      (throw (ex-info
              (str "usage: user-test study validate|plan --study FILE\n"
                   "       user-test run evaluate --study FILE --run FILE\n"
                   "       user-test project summarize --project ID --evaluations FILE\n"
                   "       user-test publication redact --input FILE")
              {:type :user-test/usage})))))

(defn -main [& args]
  (try
    (fmt/pprint (execute args))
    (catch Exception error
      (binding [*out* *err*]
        (println (.getMessage error)))
      (System/exit 2))))
