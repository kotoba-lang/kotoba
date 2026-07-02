(ns kotoba.git-adapter-test
  (:require [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [kotoba.cli :as cli]
            [kotoba.git-adapter :as git-adapter]
            [kotoba.launcher :as launcher])
  (:import [java.nio.file Files]
           [java.nio.file.attribute FileAttribute]))

(defn- fake-port
  "Recording process port that returns canned results per step id order."
  [results calls]
  (reify git-adapter/IProcess
    (-run [_ argv]
      (swap! calls conj argv)
      (nth results (dec (count @calls))))))

(def ok {:exit 0 :out "" :err ""})

(deftest plan-shapes-are-pure-data
  (is (= [["git" "init" "/r"]]
         (mapv :argv (:steps (git-adapter/plan {:positionals ["init"]
                                                :options {:repo "/r"}})))))
  (is (= [["git" "-C" "." "status" "--porcelain=v1" "--branch"]]
         (mapv :argv (:steps (git-adapter/plan {:positionals ["status"] :options {}})))))
  (is (= [["git" "-C" "/r" "add" "-A"]
          ["git" "-C" "/r" "commit" "-m" "msg"]]
         (mapv :argv (:steps (git-adapter/plan {:positionals ["commit"]
                                                :options {:repo "/r" :m "msg"}})))))
  (is (= [["git" "-C" "." "fetch" "--depth" "1" "origin"]
          ["git" "-C" "." "merge" "--ff-only" "origin/main"]]
         (mapv :argv (:steps (git-adapter/plan {:positionals ["sync"]
                                                :options {:ref "origin/main"}}))))))

(deftest plan-uses-op-option-when-no-subcommand
  (is (= :status (:operation (git-adapter/plan {:positionals [] :options {:op "status"}})))))

(deftest plan-rejects-bad-requests
  (is (= :git/missing-operation (:error (git-adapter/plan {:positionals [] :options {}}))))
  (is (= :git/unknown-operation (:error (git-adapter/plan {:positionals ["rebase"] :options {}}))))
  (is (= :git/missing-message (:error (git-adapter/plan {:positionals ["commit"] :options {}})))))

(deftest parse-status-reads-porcelain-branch-output
  (let [parsed (git-adapter/parse-status "## main...origin/main\n M src/a.clj\n?? new.txt\n")]
    (is (= "main" (:branch parsed)))
    (is (false? (:clean? parsed)))
    (is (= ["src/a.clj" "new.txt"] (mapv :path (:entries parsed)))))
  (is (true? (:clean? (git-adapter/parse-status "## main\n")))))

(defn- planned [argv-tail]
  {:kotoba.cli/ok? true
   :kotoba.cli/code :command/planned
   :kotoba.cli/data {:command :git
                     :request (cli/parse-argv argv-tail)
                     :host-action :adapter-required}})

(deftest execute-runs-steps-through-injected-port
  (let [calls (atom [])
        result (git-adapter/execute! (fake-port [ok ok] calls)
                                     (planned ["commit" "-m" "msg" "--repo" "/r"]))]
    (is (:kotoba.cli/ok? result))
    (is (= :git/executed (:kotoba.cli/code result)))
    (is (= 2 (count @calls)))
    (is (= ["git" "-C" "/r" "commit" "-m" "msg"] (last @calls)))))

(deftest execute-stops-at-first-failing-step
  (let [calls (atom [])
        result (git-adapter/execute! (fake-port [{:exit 1 :out "" :err "boom"}] calls)
                                     (planned ["commit" "-m" "msg"]))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :git/step-failed (:kotoba.cli/code result)))
    (is (= 1 (count @calls)))
    (is (= "boom" (:err (last (get-in result [:kotoba.cli/data :steps])))))))

(deftest launcher-executes-git-end-to-end
  (let [dir (str (Files/createTempDirectory "kotoba-git-adapter" (make-array FileAttribute 0)))
        init-result (launcher/dispatch ["git" "init" "--repo" dir])
        _ (spit (io/file dir "hello.txt") "hello")
        dirty (launcher/dispatch ["git" "status" "--repo" dir])]
    (is (:kotoba.cli/ok? init-result))
    (is (= :git/executed (:kotoba.cli/code init-result)))
    (is (.exists (io/file dir ".git")))
    (is (= :git/executed (:kotoba.cli/code dirty)))
    (is (false? (get-in dirty [:kotoba.cli/data :status :clean?])))
    (is (= ["hello.txt"] (mapv :path (get-in dirty [:kotoba.cli/data :status :entries]))))))
