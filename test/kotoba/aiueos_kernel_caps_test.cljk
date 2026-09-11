(ns kotoba.aiueos-kernel-caps-test
  "aiueos's default kernel capabilities (aiueos.policy/default-kernel-caps in
  aiueos-cljc-contract), registered as host-import primitives per
  ADR-2607022700 so a `.kotoba` guest component can declare and use them.
  Mirrors kotoba.cap-passing-test's direct-call (non-cap-passing) shape,
  matching how demo_providers.kotoba exercises clipboard/http/fs today.

  Each demo below is a real, capability-gated `.kotoba` -> Wasm compile: it
  denies without a policy and emits a genuine Wasm binary with one. This is
  the migration's core claim -- these aren't just contract-data entries,
  they're compiler-verified."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime])
  (:import [java.io File]))

;; wasm emit/run require a mandatory package-admission gate (F-001);
;; every dispatch call reaching those subcommands needs an admitted lock.
(def positive-lock "test/fixtures/package/positive-lock.edn")
(def trust "test/fixtures/package/trust.edn")

(defn- denied-without-policy? [demo-path]
  (let [result (launcher/dispatch ["run" demo-path "--json"])]
    (and (false? (:kotoba.cli/ok? result))
         (= :capability-not-granted
            (get-in result [:kotoba.cli/data :kotoba.runtime/result
                            :kotoba.runtime/problems 0 :kotoba.runtime/problem])))))

(defn- wasm-emits-with-policy? [demo-path policy-path expected-import]
  (let [forms (runtime/read-file demo-path :kotoba)
        policy (edn/read-string (slurp policy-path))
        wasm (runtime/wasm-binary forms policy)
        output (doto (File/createTempFile "kotoba-aiueos-demo" ".wasm") (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" demo-path "--policy" policy-path
                                    "--output" (.getPath output) "--json" "--package-lock" positive-lock "--trust" trust])]
    (and (:kotoba.wasm/ok? wasm)
         (= [expected-import] (:kotoba.wasm/imports wasm))
         (:kotoba.cli/ok? emitted)
         (= :wasm/binary-emitted (:kotoba.cli/code emitted))
         (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count]))
         (= [0 97 115 109]
            (mapv #(bit-and % 0xff)
                  (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(def device-access-demos
  "The virtio-relevant device-access quartet -- the capabilities a rewritten
  .kotoba driver component would actually call, per ADR-2607022700's
  low-trust-rewrite disposition for the retired Rust virtio.rs."
  [{:demo "src/demo_aiueos_irq.kotoba" :policy "src/demo_aiueos_irq_policy.edn"
    :import {:module "kotoba" :field "irq_subscribe" :capability "irq/subscribe"
             :params [:i32] :result :i64}}
   {:demo "src/demo_aiueos_mmio.kotoba" :policy "src/demo_aiueos_mmio_policy.edn"
    :import {:module "kotoba" :field "mmio_map" :capability "mmio/map"
             :params [:i64 :i32] :result :i64}}
   {:demo "src/demo_aiueos_dma.kotoba" :policy "src/demo_aiueos_dma_policy.edn"
    :import {:module "kotoba" :field "dma_map" :capability "dma/map"
             :params [:i32 :i32] :result :i64}}
   {:demo "src/demo_aiueos_pci.kotoba" :policy "src/demo_aiueos_pci_policy.edn"
    :import {:module "kotoba" :field "pci_config" :capability "pci/config"
             :params [:i32 :i32] :result :i32}}])

(def utility-cap-demos
  "The remaining default kernel capabilities: log/write, clock/monotonic,
  random/bytes, topic/publish, topic/subscribe (one representative demo,
  topic-poll -- topic-take/topic-count share the same capability/shape and
  are covered by the registration-completeness check below)."
  [{:demo "src/demo_aiueos_log.kotoba" :policy "src/demo_aiueos_log_policy.edn"
    :import {:module "kotoba" :field "log_write" :capability "log/write"
             :params [:i32 :i32] :result :i32}}
   {:demo "src/demo_aiueos_clock.kotoba" :policy "src/demo_aiueos_clock_policy.edn"
    :import {:module "kotoba" :field "clock_monotonic" :capability "clock/monotonic"
             :params [] :result :i64}}
   {:demo "src/demo_aiueos_random.kotoba" :policy "src/demo_aiueos_random_policy.edn"
    :import {:module "kotoba" :field "random_bytes" :capability "random/bytes"
             :params [:i32 :i32] :result :i32}}
   {:demo "src/demo_aiueos_topic_publish.kotoba" :policy "src/demo_aiueos_topic_publish_policy.edn"
    :import {:module "kotoba" :field "topic_publish" :capability "topic/publish"
             :params [:i32 :i64] :result :i32}}
   {:demo "src/demo_aiueos_topic_poll.kotoba" :policy "src/demo_aiueos_topic_poll_policy.edn"
    :import {:module "kotoba" :field "topic_poll" :capability "topic/subscribe"
             :params [:i32] :result :i64}}])

(def all-kernel-cap-demos (into device-access-demos utility-cap-demos))

(deftest all-kernel-cap-demos-deny-without-policy
  (doseq [{:keys [demo]} all-kernel-cap-demos]
    (is (denied-without-policy? demo) demo)))

(deftest all-kernel-cap-demos-compile-to-real-wasm-with-a-granting-policy
  (doseq [{:keys [demo policy import]} all-kernel-cap-demos]
    (is (wasm-emits-with-policy? demo policy import) demo)))

(deftest all-nine-aiueos-kernel-capabilities-are-registered
  ;; log/write, clock/monotonic, random/bytes, topic/publish, topic/subscribe
  ;; (backing poll/take/count), pci/config, dma/map, irq/subscribe, mmio/map --
  ;; aiueos.policy/default-kernel-caps in aiueos-cljc-contract.
  (doseq [op '[log-write clock-monotonic random-bytes topic-publish
               topic-poll topic-take topic-count pci-config dma-map
               irq-subscribe mmio-map]]
    (is (contains? runtime/host-imports op) (str op " missing from host-imports"))
    (is (contains? runtime/op->kind op) (str op " missing from op->kind"))))
