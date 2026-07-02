(ns kotoba.test-runner
  "Aggregate test entry point for `clojure -M:test`."
  (:require [clojure.test :refer [run-tests]]
            [kotoba.host-providers-test]
            [kotoba.launcher-test]
            [kotoba.package-admission-test]))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.host-providers-test
                                        'kotoba.launcher-test
                                        'kotoba.package-admission-test)]
    (when (pos? (+ (or fail 0) (or error 0)))
      (System/exit 1))))
