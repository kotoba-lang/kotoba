(ns kotoba.rad-adapter-portable-test
  "The genuinely portable slice of kotoba.rad-adapter-test: pure
  scaffold/plan/execute! coverage through an injected IRadHost port.
  `launcher-executes-rad-lifecycle-end-to-end` stays in
  kotoba.rad-adapter-test (.clj) because it drives kotoba.launcher/dispatch
  through a real `kotoba wasm emit` compile over java.nio.file -- a real JVM
  boundary, not a portability gap."
  (:require [clojure.edn :as edn]
            #?(:clj [clojure.test :refer [deftest is]]
               :cljs [cljs.test :refer [deftest is] :include-macros true])
            [kotoba.cli :as cli]
            [kotoba.rad-adapter :as rad-adapter]))

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
    (is (re-find #"\(ns my-app\)" (files "src/my_app.kotoba")))
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
