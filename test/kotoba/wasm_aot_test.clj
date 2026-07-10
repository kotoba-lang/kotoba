(ns kotoba.wasm-aot-test
  "Locks the safe Kotoba → WASM AOT path: portable unsigned byte vectors,
  golden digests, and CLI aliases (emit / safe-build / build)."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime]
            [kotoba.wasm.bytes :as wasm-bytes]))

(def ^:private positive-lock "test/fixtures/package/positive-lock.edn")
(def ^:private trust "test/fixtures/package/trust.edn")

(defn- golden-sha [name]
  (str/trim (slurp (str "test/kotoba/wasm/goldens/" name ".sha256"))))

(defn- golden-bytes [name]
  (edn/read-string (slurp (str "test/kotoba/wasm/goldens/" name ".bytes.edn"))))

(deftest wasm-binary-exposes-portable-unsigned-bytes
  (let [forms (runtime/read-file "src/demo.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm))
    (is (vector? (:kotoba.wasm/bytes wasm)))
    (is (every? #(and (integer? %) (<= 0 % 255)) (:kotoba.wasm/bytes wasm)))
    (is (= (:kotoba.wasm/byte-count wasm) (count (:kotoba.wasm/bytes wasm))))
    (is (wasm-bytes/magic? (:kotoba.wasm/bytes wasm)))
    (is (= (mapv #(bit-and % 0xff) (take 8 (:kotoba.wasm/binary wasm)))
           (vec (take 8 (:kotoba.wasm/bytes wasm)))))))

(deftest wasm-aot-demo-matches-golden-digest
  (let [forms (runtime/read-file "src/demo.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        sha (wasm-bytes/hex-sha256 (:kotoba.wasm/bytes wasm))]
    (is (= (golden-sha "demo") sha))
    (is (= (golden-bytes "demo") (:kotoba.wasm/bytes wasm)))))

(deftest wasm-aot-demo-call-matches-golden-digest
  (let [forms (runtime/read-file "src/demo_call.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        sha (wasm-bytes/hex-sha256 (:kotoba.wasm/bytes wasm))]
    (is (= (golden-sha "demo_call") sha))
    (is (= (golden-bytes "demo_call") (:kotoba.wasm/bytes wasm)))))

(deftest wasm-aot-fact-matches-golden-digest
  (let [path "../kototama/test/kototama/fixtures/kotoba-compiled-fact.kotoba"]
    (when (.exists (io/file path))
      (let [forms (runtime/read-file path :kotoba)
            wasm (runtime/wasm-binary forms)
            sha (wasm-bytes/hex-sha256 (:kotoba.wasm/bytes wasm))]
        (is (= (golden-sha "fact") sha))
        (is (= (golden-bytes "fact") (:kotoba.wasm/bytes wasm)))))))

(deftest wasm-safe-build-and-build-are-emit-aliases
  (testing "safe-build and build share emit semantics"
    (let [emit (launcher/dispatch ["wasm" "emit" "src/demo.kotoba"
                                   "--package-lock" positive-lock "--trust" trust "--json"])
          safe (launcher/dispatch ["wasm" "safe-build" "src/demo.kotoba"
                                   "--package-lock" positive-lock "--trust" trust "--json"])
          build (launcher/dispatch ["wasm" "build" "src/demo.kotoba"
                                    "--package-lock" positive-lock "--trust" trust "--json"])]
      (is (:kotoba.cli/ok? emit))
      (is (:kotoba.cli/ok? safe))
      (is (:kotoba.cli/ok? build))
      (is (= :wasm/binary-emitted (:kotoba.cli/code emit)))
      (is (= :wasm/binary-emitted (:kotoba.cli/code safe)))
      (is (= :wasm/binary-emitted (:kotoba.cli/code build)))
      (is (= (get-in emit [:kotoba.cli/data :kotoba.wasm/byte-count])
             (get-in safe [:kotoba.cli/data :kotoba.wasm/byte-count])))
      (is (= (get-in emit [:kotoba.cli/data :kotoba.wasm/byte-count])
             (get-in build [:kotoba.cli/data :kotoba.wasm/byte-count]))))))

(deftest run-engine-wasm-aot-executes-demo
  (let [via-wasm-run (launcher/dispatch ["wasm" "run" "src/demo.kotoba"
                                         "--package-lock" positive-lock "--trust" trust "--json"])
        via-run-engine (launcher/dispatch ["run" "src/demo.kotoba" "--engine" "wasm"
                                           "--package-lock" positive-lock "--trust" trust "--json"])]
    (is (:kotoba.cli/ok? via-wasm-run))
    (is (= :wasm/run-completed (:kotoba.cli/code via-wasm-run)))
    (is (= 42 (get-in via-wasm-run [:kotoba.cli/data :kotoba.wasm/value])))
    (is (:kotoba.cli/ok? via-run-engine))
    (is (= :wasm/run-completed (:kotoba.cli/code via-run-engine)))
    (is (= 42 (get-in via-run-engine [:kotoba.cli/data :kotoba.wasm/value])))))
