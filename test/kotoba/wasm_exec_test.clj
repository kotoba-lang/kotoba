(ns kotoba.wasm-exec-test
  "Proves `kotoba.runtime/wasm-binary` emits genuinely EXECUTABLE modules —
  not merely byte-structure-valid ones — by running them through
  com.dylibso.chicory (a real, pure-JVM WASM engine) and observing real
  kgraph-* host-import effects, exactly as a production host (browser,
  Cloudflare Worker) would see them."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(deftest wasm-binary-actually-executes
  (testing "a trivial (no-import) module runs through Chicory and returns the interpreted value"
    (let [forms (runtime/read-file "src/demo.kotoba" :kotoba)
          interpreted (runtime/run (launcher/safe-analyzer-fact-classification)
                                   (launcher/source-plan "src/demo.kotoba")
                                   forms)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= (:kotoba.runtime/value interpreted)
             (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest wasm-binary-runs-kgraph-round-trip-through-real-host-functions
  (testing "compile -> emit -> Chicory-execute: kgraph-assert! really writes, kgraph-query really reads it back"
    (let [forms (runtime/read-file "src/demo_kgraph.kotoba" :kotoba)
          policy (edn/read-string (slurp "src/demo_kgraph_policy.edn"))
          checked (runtime/check (launcher/safe-analyzer-fact-classification)
                                 (launcher/source-plan "src/demo_kgraph.kotoba")
                                 forms policy)
          wasm (runtime/wasm-binary forms policy)
          store (atom [])
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (wasm-exec/kgraph-host-functions store))
          result (.apply (.export instance "main") (long-array 0))
          written (aget ^longs result 0)
          ;; `buf` = the first (and only) `alloc` call in demo_kgraph.kotoba's
          ;; `main`, which returns the heap pointer's value BEFORE bumping —
          ;; i.e. exactly `:kotoba.wasm/heap-base` (kotoba.runtime/wasm-binary
          ;; already computes and reports this; no need to hardcode it here).
          buf-ptr (:kotoba.wasm/heap-base wasm)]
      (is (:kotoba.runtime/ok? checked) "static capability check admits :graph/kotoba")
      (is (:kotoba.wasm/ok? wasm))
      (is (= [{:module "kotoba" :field "kgraph_assert" :capability "graph/kotoba"
               :params [:i32 :i32] :result :i32}
              {:module "kotoba" :field "kgraph_query" :capability "graph/kotoba"
               :params [:i32 :i32 :i32 :i32] :result :i32}]
             (:kotoba.wasm/imports wasm))
          "only the two host imports the source actually calls are declared")
      (is (pos? written) "kgraph_query wrote a real result into the guest buffer")
      (is (= [["Aoi"]]
             (edn/read-string (wasm-exec/read-memory-string instance buf-ptr written)))
          "the query result read back out of guest memory matches the datom asserted moments earlier")
      (is (= [[1 :name "Aoi"]] @store)
          "the host-side kgraph store really received the asserted datom (not a 0-returning stub)"))))
