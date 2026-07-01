(ns kotoba.launcher-test
  (:require [clojure.data.json :as json]
            [clojure.test :refer [deftest is run-tests]]
            [kotoba.launcher :as launcher]))

(deftest delegates-check-to-cljc-authority
  (let [result (launcher/dispatch ["check" "--kind" "cli-contract" "--json"])]
    (is (:kotoba.cli/ok? result))
    (is (= :contract/valid (:kotoba.cli/code result)))
    (is (true? (get (json/read-str (launcher/render-result result true))
                    "kotoba.cli/ok?")))))

(deftest side-effecting-commands-stay-data
  (let [result (launcher/dispatch ["deploy" "--manifest" "package-manifest.edn" "--target" "dev"])]
    (is (:kotoba.cli/ok? result))
    (is (= :command/planned (:kotoba.cli/code result)))
    (is (= :adapter-required (get-in result [:kotoba.cli/data :host-action])))))

(deftest returns-nonzero-for-unknown-command
  (let [result (launcher/dispatch ["unknown"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= 1 (launcher/result->exit result)))))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.launcher-test)]
    (when (pos? (+ (or fail 0) (or error 0)))
      (System/exit 1))))
