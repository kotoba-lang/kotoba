(ns kotoba.git-adapter-test
  "The JVM-only slice of kotoba.git-adapter coverage: a real `git` subprocess
  shelled out to through kotoba.launcher/dispatch, over a java.nio.file temp
  directory. The genuinely portable coverage (pure plan/parse-status/execute!
  through an injected IProcess port) lives in
  kotoba.git-adapter-portable-test (.cljc), registered on both hosts."
  (:require [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [kotoba.launcher :as launcher])
  (:import [java.nio.file Files]
           [java.nio.file.attribute FileAttribute]))

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
