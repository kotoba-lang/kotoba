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

(deftest wasm-binary-executes-f32-arithmetic-and-comparison
  (testing "f32 literal/f32+/f32> compile to a real, executable Chicory module: (1.5+2.5) > 3.0 -> 1"
    (let [forms (runtime/read-file "src/demo_f32.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 1 (long (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))))))

(deftest wasm-binary-executes-f32-fn-params-and-result
  (testing "f32-typed user fn params/results + f32sqrt: sqrt(8.0 * 2.0) = 4.0"
    (let [forms (runtime/read-file "src/demo_f32_result.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= :f32 (:kotoba.wasm/result-type wasm)))
      (is (== 4.0 (double (wasm-exec/run-main (:kotoba.wasm/binary wasm) [] nil :f32)))))))

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

(deftest has-capability-runtime-check-reflects-the-run-time-policy-not-a-stub
  (testing "the SAME compiled bytes answer has-capability? differently depending on the POLICY
            instantiate/run-main is given at RUN time -- proving the runtime check is real (maps
            the i32 id back to a capability name and consults a policy), not the old always-1
            always-grant stub that ignored both the id and any policy"
    (let [forms (runtime/read-file "src/demo_cap.kotoba" :kotoba)
          policy (edn/read-string (slurp "src/demo_policy.edn"))
          checked (runtime/check (launcher/safe-analyzer-fact-classification)
                                 (launcher/source-plan "src/demo_cap.kotoba")
                                 forms policy)
          wasm (runtime/wasm-binary forms policy)
          bytes (:kotoba.wasm/binary wasm)]
      (is (:kotoba.runtime/ok? checked) "static compile-time check admits :notify/show under `policy`")
      (is (:kotoba.wasm/ok? wasm))
      (testing "granted: a run-time policy that DOES include :notify/show observes true (bump 6 = 7)"
        (is (= 7 (wasm-exec/run-main bytes [] policy))))
      (testing "denied: the identical bytes, run under a policy that does NOT include :notify/show,
                observe false (0) -- this is the case the old stub could never produce"
        (is (= 0 (wasm-exec/run-main bytes [] {}))))
      (testing "denied by default: no policy argument at all also denies (fail closed, not fail open)"
        (is (= 0 (wasm-exec/run-main bytes [])))))))

(deftest guarded-kgraph-host-functions-deny-blocks-the-effect
  (testing "kgraph-host-functions' guarded (2-/3-arg) form really stops kgraph_assert from ever
            touching the store when the RUN-time policy doesn't grant :graph/kotoba -- proving the
            effectful kgraph-* host imports, not just has-capability?, get real per-call
            enforcement at the execution boundary, mirroring kotoba.host-providers/host-call's
            fail-closed dispatch for the interpreter path"
    (let [forms (runtime/read-file "src/demo_kgraph.kotoba" :kotoba)
          compile-policy (edn/read-string (slurp "src/demo_kgraph_policy.edn"))
          checked (runtime/check (launcher/safe-analyzer-fact-classification)
                                 (launcher/source-plan "src/demo_kgraph.kotoba")
                                 forms compile-policy)
          wasm (runtime/wasm-binary forms compile-policy)
          store (atom [])
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (wasm-exec/kgraph-host-functions store {}))
          denial (try
                   (.apply (.export instance "main") (long-array 0))
                   nil
                   (catch clojure.lang.ExceptionInfo e (ex-data e)))]
      (is (:kotoba.runtime/ok? checked) "static check admits :graph/kotoba at compile time")
      (is (:kotoba.wasm/ok? wasm))
      (is (some? denial) "the guarded kgraph-assert! call was denied, not silently allowed through")
      (is (= :empty-intersection (:kotoba.host/denied denial)))
      (is (= 'kgraph-assert! (:kotoba.host/call denial)))
      (is (= [] @store)
          "the store was never touched -- the guard denied BEFORE the effect ran, not after"))))

(deftest guarded-kgraph-host-functions-grant-allows-the-effect
  (testing "the same guarded path performs the real effect (unchanged behavior) when the run-time
            policy DOES grant :graph/kotoba"
    (let [forms (runtime/read-file "src/demo_kgraph.kotoba" :kotoba)
          policy (edn/read-string (slurp "src/demo_kgraph_policy.edn"))
          wasm (runtime/wasm-binary forms policy)
          store (atom [])
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (wasm-exec/kgraph-host-functions store policy))
          result (.apply (.export instance "main") (long-array 0))]
      (is (:kotoba.wasm/ok? wasm))
      (is (pos? (aget ^longs result 0)))
      (is (= [[1 :name "Aoi"]] @store)))))

(deftest fuel-limit-traps-a-genuinely-unbounded-guest
  (testing "a deliberately self-recursive, never-terminating guest (src/demo_loop_forever.kotoba:
            `spin` calls itself unconditionally, `main` calls `spin`, neither ever returns) is
            trapped by the fuel limit instead of hanging the test process or blowing the JVM call
            stack uncontrolled. A small explicit :kotoba.policy/fuel keeps this well under any
            real JVM stack-overflow depth, so the trap -- not a StackOverflowError -- is what
            actually fires."
    (let [forms (runtime/read-file "src/demo_loop_forever.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)
          bytes (:kotoba.wasm/binary wasm)
          trapped (try
                    (wasm-exec/run-main bytes [] {:kotoba.policy/fuel 200})
                    ::did-not-trap
                    (catch clojure.lang.ExceptionInfo e (ex-data e)))]
      (is (:kotoba.wasm/ok? wasm))
      (is (not= ::did-not-trap trapped) "execution must not run to completion -- `spin` never returns")
      (is (= :fuel-exhausted (:kotoba.wasm/problem trapped)))
      (is (= 200 (:kotoba.wasm/fuel-limit trapped))))))
