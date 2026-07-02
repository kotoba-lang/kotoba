(ns kotoba.aiueos-kernel-caps-test
  "aiueos's default kernel capabilities (aiueos.policy/default-kernel-caps in
  aiueos-cljc-contract), registered as host-import primitives per
  ADR-2607022700 so a `.kotoba` guest component can declare and use them.
  Mirrors kotoba.cap-passing-test's direct-call (non-cap-passing) shape,
  matching how demo_providers.kotoba exercises clipboard/http/fs today."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime])
  (:import [java.io File]))

(deftest irq-subscribe-denied-without-policy
  (let [result (launcher/dispatch ["run" "src/demo_aiueos_irq.kotoba" "--json"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :capability-not-granted
           (get-in result [:kotoba.cli/data :kotoba.runtime/result
                           :kotoba.runtime/problems 0 :kotoba.runtime/problem])))))

(deftest wasm-emit-supports-irq-subscribe-with-a-granting-policy
  (let [forms (runtime/read-file "src/demo_aiueos_irq.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_aiueos_irq_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (File/createTempFile "kotoba-demo-aiueos-irq" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_aiueos_irq.kotoba"
                                    "--policy" "src/demo_aiueos_irq_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i64 (:kotoba.wasm/result-type wasm)))
    (is (= [{:module "kotoba"
             :field "irq_subscribe"
             :capability "irq/subscribe"
             :params [:i32]
             :result :i64}]
           (:kotoba.wasm/imports wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= :wasm/binary-emitted (:kotoba.cli/code emitted)))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff)
                 (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest mmio-map-denied-without-policy
  (let [result (launcher/dispatch ["run" "src/demo_aiueos_mmio.kotoba" "--json"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :capability-not-granted
           (get-in result [:kotoba.cli/data :kotoba.runtime/result
                           :kotoba.runtime/problems 0 :kotoba.runtime/problem])))))

(deftest wasm-emit-supports-mmio-map-with-a-granting-policy
  (let [forms (runtime/read-file "src/demo_aiueos_mmio.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_aiueos_mmio_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (File/createTempFile "kotoba-demo-aiueos-mmio" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_aiueos_mmio.kotoba"
                                    "--policy" "src/demo_aiueos_mmio_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i64 (:kotoba.wasm/result-type wasm)))
    (is (= [{:module "kotoba"
             :field "mmio_map"
             :capability "mmio/map"
             :params [:i64 :i32]
             :result :i64}]
           (:kotoba.wasm/imports wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= :wasm/binary-emitted (:kotoba.cli/code emitted)))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff)
                 (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest all-nine-aiueos-kernel-capabilities-are-registered
  ;; log/write, clock/monotonic, random/bytes, topic/publish, topic/subscribe
  ;; (backing poll/take/count), pci/config, dma/map, irq/subscribe, mmio/map --
  ;; aiueos.policy/default-kernel-caps in aiueos-cljc-contract.
  (doseq [op '[log-write clock-monotonic random-bytes topic-publish
               topic-poll topic-take topic-count pci-config dma-map
               irq-subscribe mmio-map]]
    (is (contains? runtime/host-imports op) (str op " missing from host-imports"))
    (is (contains? runtime/op->kind op) (str op " missing from op->kind"))))
