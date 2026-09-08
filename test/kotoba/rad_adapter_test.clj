(ns kotoba.rad-adapter-test
  "The JVM-only slice of kotoba.rad-adapter coverage:
  `launcher-executes-rad-lifecycle-end-to-end` drives kotoba.launcher/dispatch
  through a real `kotoba wasm emit` compile over a java.nio.file temp
  directory. The genuinely portable coverage (pure scaffold/plan/execute!
  through an injected IRadHost port) lives in
  kotoba.rad-adapter-portable-test (.cljc), registered on both hosts."
  (:require [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [kotoba.launcher :as launcher])
  (:import [java.nio.file Files]
           [java.nio.file.attribute FileAttribute]))

(deftest launcher-executes-rad-lifecycle-end-to-end
  (let [dir (str (Files/createTempDirectory "kotoba-rad-adapter" (make-array FileAttribute 0))
                 "/demo-app")
        new-result (launcher/dispatch ["rad" "new" "--project" dir])
        test-result (launcher/dispatch ["rad" "test" "--project" dir])
        build-result (launcher/dispatch ["rad" "build" "--project" dir])
        export-path (str dir "/dist/demo.wasm")
        export-result (launcher/dispatch ["rad" "export" "--project" dir "-o" export-path])]
    (is (= :rad/executed (:kotoba.cli/code new-result)))
    (is (.exists (io/file dir "src/demo_app.kotoba")))
    (is (.exists (io/file dir "package.edn")))
    (is (= :rad/executed (:kotoba.cli/code test-result)))
    (is (= :check/valid
           (get-in test-result [:kotoba.cli/data :steps 0 :result :kotoba.cli/code])))
    (is (= :rad/executed (:kotoba.cli/code build-result)))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff)
                 (take 4 (Files/readAllBytes
                          (.toPath (io/file dir "target/demo_app.wasm")))))))
    (is (= :rad/executed (:kotoba.cli/code export-result)))
    (is (.exists (io/file export-path)))))
