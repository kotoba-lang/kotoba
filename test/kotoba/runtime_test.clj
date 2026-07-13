(ns kotoba.runtime-test
  "Regression coverage for `kotoba.runtime/read-forms`/`read-file`'s reader
  safety: `.kotoba` source is untrusted input (the whole point of the
  safe-subset checker downstream), so the reader itself must never be able
  to execute code -- `clojure.tools.reader/*read-eval*` defaults to true,
  which lets `#=(...)` run arbitrary JVM code at READ time, before the
  checker or any capability policy ever runs."
  (:require [clojure.java.io :as io]
            [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]))

(deftest read-forms-rejects-the-eval-reader
  (testing "a `.kotoba` source containing #=(...) must be rejected at read
            time, not executed"
    (let [payload "(defn main [] 1)\n#=(+ 1 2)\n"]
      (is (thrown-with-msg? Exception #"read-eval"
                            (runtime/read-forms payload :clj))))))

(deftest read-file-rejects-the-eval-reader-and-never-touches-the-filesystem
  (testing "the same rejection holds through read-file, and — the actual
            exploit shape — a side-effecting payload never runs (no file
            gets written)"
    (let [tmp (java.io.File/createTempFile "kotoba-rce-poc" ".kotoba")
          target (java.io.File/createTempFile "kotoba-rce-poc-pwned" ".txt")]
      (.delete target)
      (try
        (spit tmp (str "(defn main [] 1)\n"
                      "#=(spit \"" (.getAbsolutePath target) "\" \"pwned\")\n"))
        (is (thrown? Exception (runtime/read-file (.getPath tmp) :clj)))
        (is (not (.exists target))
            "the eval-reader payload must never have run, so the target file
             must not exist")
        (finally
          (io/delete-file tmp true)
          (io/delete-file target true))))))
