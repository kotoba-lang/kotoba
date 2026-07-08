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

(deftest wasm-binary-executes-every-f32-comparison-and-neg
  (testing "f32=/f32</f32<=/f32>=/f32neg (previously zero coverage) all wired correctly, incl. a false-expected check (f32> 1.0 2.0)"
    (let [forms (runtime/read-file "src/demo_f32_ops.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 1 (long (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))
          "1 means every true-expected comparison passed AND f32> correctly returned false for 1.0>2.0 (a -1 would mean that comparison is backwards, 0 would mean some other check failed)"))))

(deftest f32sqrt-and-f32neg-reject-wrong-arity
  (testing "f32sqrt/f32neg -- unlike (f32 ...) which already checked arity -- previously had no arity check at all: (f32sqrt) silently took nil as its argument (:unsupported-form, not :arity) and (f32sqrt a b) silently dropped the extra arg"
    (let [locals {}
          too-few (runtime/compile-wasm-expr '(f32sqrt) locals)
          too-many (runtime/compile-wasm-expr (list 'f32sqrt '(f32 1.0) '(f32 2.0)) locals)
          neg-too-few (runtime/compile-wasm-expr '(f32neg) locals)]
      (is (= :arity (get-in too-few [:problem :kotoba.wasm/problem])))
      (is (= "f32sqrt" (get-in too-few [:problem :kotoba.wasm/op])))
      (is (= :arity (get-in too-many [:problem :kotoba.wasm/problem])))
      (is (= 2 (get-in too-many [:problem :kotoba.wasm/actual])))
      (is (= :arity (get-in neg-too-few [:problem :kotoba.wasm/problem])))
      (is (= "f32neg" (get-in neg-too-few [:problem :kotoba.wasm/op]))))))

(deftest typed-fold-ops-reject-mixed-arg-types
  (testing "compile-wasm-fold-type (backing f32+/f32-/f32*/f32div and i64+/i64-/i64*)
            had zero direct test coverage of its :type-mismatch branch -- only ever
            exercised via all-same-type happy-path .kotoba fixtures. Mixing a typed
            literal with an untyped (defaults to :i32) literal, in either argument
            position, must be rejected at compile time rather than silently emitting
            a WASM module with a mismatched operand type Chicory would trap on."
    (let [locals {}
          f32-typed-then-untyped (runtime/compile-wasm-expr (list 'f32+ '(f32 1.0) 42) locals)
          f32-untyped-then-typed (runtime/compile-wasm-expr (list 'f32+ 42 '(f32 1.0)) locals)
          f32-single-untyped (runtime/compile-wasm-expr (list 'f32+ 42) locals)
          i64-typed-then-untyped (runtime/compile-wasm-expr (list 'i64+ '(i64 1) 42) locals)
          i64-untyped-then-typed (runtime/compile-wasm-expr (list 'i64+ 42 '(i64 1)) locals)]
      (is (= :type-mismatch (get-in f32-typed-then-untyped [:problem :kotoba.wasm/problem])))
      (is (= :f32 (get-in f32-typed-then-untyped [:problem :kotoba.wasm/expected])))
      (is (= :type-mismatch (get-in f32-untyped-then-typed [:problem :kotoba.wasm/problem]))
          "the mismatch must be caught regardless of which argument position is untyped")
      (is (= :type-mismatch (get-in f32-single-untyped [:problem :kotoba.wasm/problem]))
          "a single untyped arg to a typed fold op is still a mismatch, not a pass-through")
      (is (= :type-mismatch (get-in i64-typed-then-untyped [:problem :kotoba.wasm/problem])))
      (is (= :i64 (get-in i64-typed-then-untyped [:problem :kotoba.wasm/expected])))
      (is (= :type-mismatch (get-in i64-untyped-then-typed [:problem :kotoba.wasm/problem]))))))

(deftest typed-fold-ops-accept-consistent-types-and-tag-result-type
  (testing "the non-mismatch path of compile-wasm-fold-type: same-type args compile
            cleanly and the fold's own result is tagged with the declared type (not
            left as whatever compile-wasm-fold's bare fold would produce)"
    (let [locals {}
          f32-two-args (runtime/compile-wasm-expr (list 'f32+ '(f32 1.0) '(f32 2.0)) locals)
          f32-single-arg (runtime/compile-wasm-expr (list 'f32+ '(f32 1.0)) locals)
          i64-two-args (runtime/compile-wasm-expr (list 'i64+ '(i64 1) '(i64 2)) locals)]
      (is (nil? (:problem f32-two-args)))
      (is (= :f32 (:result-type f32-two-args)))
      (is (nil? (:problem f32-single-arg)))
      (is (= :f32 (:result-type f32-single-arg))
          "single-arg fold-type still gets the declared result-type tagged, not left untagged from the compile-wasm-fold pass-through")
      (is (nil? (:problem i64-two-args)))
      (is (= :i64 (:result-type i64-two-args))))))

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
