(ns kotoba.rad-adapter-test
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [kotoba.cli :as cli]
            [kotoba.launcher :as launcher]
            [kotoba.rad-adapter :as rad-adapter])
  (:import [java.nio.file Files]
           [java.nio.file.attribute FileAttribute]))

(defn- fake-host
  "Recording rad host; -dispatch returns canned results in call order."
  [dispatch-results calls]
  (let [dispatched (atom 0)]
    (reify rad-adapter/IRadHost
      (-mkdirs [_ path] (swap! calls conj [:mkdirs path]))
      (-write-file [_ path content] (swap! calls conj [:write path content]))
      (-dispatch [_ argv]
        (swap! calls conj [:dispatch argv])
        (nth dispatch-results (dec (swap! dispatched inc)))))))

(def ok-dispatch {:kotoba.cli/ok? true :kotoba.cli/code :check/valid})

(deftest scaffold-files-are-pure-data
  (let [files (rad-adapter/scaffold-files "/tmp/my-app" "app")]
    (is (= #{"src/my_app.kotoba" "package.edn" "kotoba.lock.edn" "README.md"} (set (keys files))))
    (is (.contains ^String (files "src/my_app.kotoba") "(ns my-app)"))
    (let [manifest (edn/read-string (files "package.edn"))]
      (is (= "my-app" (:kotoba.package/name manifest)))
      (is (true? (:kotoba.package/draft? manifest))))
    (let [lock (edn/read-string (files "kotoba.lock.edn"))]
      (is (= 1 (:kotoba.lock/version lock)))
      (is (= [] (:deps lock))))))

(deftest plan-shapes-per-operation
  (let [new-plan (rad-adapter/plan {:positionals ["new"] :options {:project "/p/app"}})
        build-plan (rad-adapter/plan {:positionals ["build"] :options {:project "/p/app"}})
        test-plan (rad-adapter/plan {:positionals ["test"] :options {:project "/p/app"}})
        export-plan (rad-adapter/plan {:positionals ["export"]
                                       :options {:project "/p/app" :o "/out/app.wasm"}})]
    (is (= [:fs/mkdirs :fs/write :fs/write :fs/write :fs/write]
           (mapv :kind (:steps new-plan))))
    (is (= ["wasm" "emit" "/p/app/src/app.kotoba" "--package-lock" "/p/app/kotoba.lock.edn" "--output" "/p/app/target/app.wasm"]
           (:argv (second (:steps build-plan)))))
    (is (= [["check" "/p/app/src/app.kotoba"]]
           (mapv :argv (:steps test-plan))))
    (is (= ["wasm" "emit" "/p/app/src/app.kotoba" "--package-lock" "/p/app/kotoba.lock.edn" "--output" "/out/app.wasm"]
           (:argv (second (:steps export-plan)))))))

(deftest plan-rejects-bad-requests
  (is (= :rad/missing-operation (:error (rad-adapter/plan {:positionals [] :options {}}))))
  (is (= :rad/unknown-operation (:error (rad-adapter/plan {:positionals ["deploy"] :options {}}))))
  (is (= :rad/missing-output (:error (rad-adapter/plan {:positionals ["export"] :options {}})))))

(defn- planned [argv-tail]
  {:kotoba.cli/ok? true
   :kotoba.cli/code :command/planned
   :kotoba.cli/data {:command :rad
                     :request (cli/parse-argv argv-tail)
                     :host-action :adapter-required}})

(deftest execute-runs-steps-through-injected-host
  (let [calls (atom [])
        result (rad-adapter/execute! (fake-host [ok-dispatch] calls)
                                     (planned ["test" "--project" "/p/app"]))]
    (is (:kotoba.cli/ok? result))
    (is (= :rad/executed (:kotoba.cli/code result)))
    (is (= [[:dispatch ["check" "/p/app/src/app.kotoba"]]] @calls))
    (is (= :check/valid
           (get-in result [:kotoba.cli/data :steps 0 :result :kotoba.cli/code])))))

(deftest execute-stops-at-first-failing-step
  (let [calls (atom [])
        result (rad-adapter/execute!
                (fake-host [{:kotoba.cli/ok? false :kotoba.cli/code :check/invalid}] calls)
                (planned ["test" "--project" "/p/app"]))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :rad/step-failed (:kotoba.cli/code result)))
    (is (= 1 (count @calls)))))

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
