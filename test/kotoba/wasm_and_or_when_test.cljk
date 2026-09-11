(ns kotoba.wasm-and-or-when-test
  "Regression coverage for kotoba-lang/kotoba-lang's `and`/`or`/`when` WASM
  code-generation gap: `kotoba.runtime/source-problems` (the static
  safety checker) never denied these three forms -- they simply aren't
  members of :non-executable-forms -- so `runtime/check` reported
  :kotoba.runtime/ok? true for source using them, but
  `kotoba.runtime/compile-wasm-expr`'s WASM code-generator had no `case`
  branch for any of the three, so `kotoba wasm emit` failed every one of
  them with `{:kotoba.wasm/problem :unsupported-op :kotoba.wasm/op \"and\"}`
  (`\"or\"`, `\"when\"` respectively) -- a real compile -> emit -> Chicory
  gap between what the checker admitted and what the emitter could
  produce. See orgs/cloud-itonami/cloud-itonami-isic-6511/wasm/README.md's
  \"Language-subset finding worth flagging\" section for the original
  discovery.

  Proves, through the SAME real (non-mock) compile -> emit -> Chicory-
  execute path `kotoba.wasm-exec-test` uses elsewhere in this suite:
  1. `kotoba wasm emit` now succeeds for all three ops (the exact failure
     this test suite would have caught before the fix).
  2. Their compiled WASM produces the correct short-circuit VALUE
     semantics (kotoba's i32 0/nonzero truthiness).
  3. Their compiled WASM performs REAL short-circuit CONTROL FLOW, not
     just a value that happens to look right -- a would-be-infinite guest
     call sits in the branch that must never execute, and a fuel-limited
     run proves it really isn't (contrasted against a sanity case where
     the same call, deliberately reached, does trap on fuel exhaustion)."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run
  "Compile SRC (a `.kotoba` source string) to WASM and execute its `main`
  through a real Chicory instance, returning the i64/i32 result. POLICY, if
  given, is passed through to wasm-exec/run-main (e.g. :kotoba.policy/fuel)."
  ([src] (emit-and-run src nil))
  ([src policy]
   (let [forms (runtime/read-forms src :kotoba)
         wasm (runtime/wasm-binary forms)]
     (is (:kotoba.wasm/ok? wasm)
         (str "kotoba wasm emit should succeed: " (:kotoba.wasm/problems wasm)))
     (wasm-exec/run-main (:kotoba.wasm/binary wasm) [] policy))))

(deftest and-emits-and-returns-last-truthy-value
  (testing "(and 3 4 5): all args truthy -> the last value (real fixture, src/demo_and.kotoba)"
    (let [forms (runtime/read-file "src/demo_and.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm) "and is no longer :unsupported-op")
      (is (= 5 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest and-short-circuits-on-a-falsy-arg-without-evaluating-the-rest
  (testing "(and 0 (spin 0)): falsy first arg must skip the never-returning second arg
            entirely (real fixture, src/demo_and_short_circuit.kotoba) -- proven by
            completing under a tiny fuel budget that a real evaluation of `spin` would
            exhaust"
    (let [forms (runtime/read-file "src/demo_and_short_circuit.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 0 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []
                                   {:kotoba.policy/fuel 200}))
          "returns 0 without ever reaching (spin 0)"))))

(deftest and-inline-variants-cover-arity-and-falsy-in-middle
  (testing "1-arg and is the identity"
    (is (= 5 (emit-and-run "(ns t)\n(defn main [] (and 5))"))))
  (testing "2-arg and, both truthy -> last"
    (is (= 2 (emit-and-run "(ns t)\n(defn main [] (and 1 2))"))))
  (testing "2-arg and, second falsy -> 0 (the falsy value itself, not the first)"
    (is (= 0 (emit-and-run "(ns t)\n(defn main [] (and 1 0))"))))
  (testing "3-arg and, falsy in the MIDDLE short-circuits before the third arg"
    (is (= 0 (emit-and-run "(ns t)\n(defn main [] (and 3 0 5))"))))
  (testing "and composes with comparison ops, matching typical boolean-combinator usage"
    (is (= 1 (emit-and-run "(ns t)\n(defn main [] (and (> 5 3) (< 2 4)))")))))

(deftest or-emits-and-returns-first-truthy-value
  (testing "(or 0 7): falls through the falsy first arg to the truthy second (real
            fixture, src/demo_or.kotoba)"
    (let [forms (runtime/read-file "src/demo_or.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm) "or is no longer :unsupported-op")
      (is (= 7 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest or-short-circuits-on-a-truthy-arg-without-evaluating-the-rest
  (testing "(or 7 (spin 0)): truthy first arg must skip the never-returning second arg
            entirely (real fixture, src/demo_or_short_circuit.kotoba) -- proven by
            completing under a tiny fuel budget"
    (let [forms (runtime/read-file "src/demo_or_short_circuit.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 7 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []
                                   {:kotoba.policy/fuel 200}))
          "returns 7 without ever reaching (spin 0)"))))

(deftest or-inline-variants-cover-arity-and-all-falsy
  (testing "1-arg or is the identity"
    (is (= 0 (emit-and-run "(ns t)\n(defn main [] (or 0))"))))
  (testing "2-arg or, first truthy -> first"
    (is (= 7 (emit-and-run "(ns t)\n(defn main [] (or 7 3))"))))
  (testing "all-falsy or returns the last (falsy) value"
    (is (= 0 (emit-and-run "(ns t)\n(defn main [] (or 0 0))"))))
  (testing "3-arg or, first two falsy -> third"
    (is (= 9 (emit-and-run "(ns t)\n(defn main [] (or 0 0 9))"))))
  (testing "or composes with comparison ops"
    (is (= 1 (emit-and-run "(ns t)\n(defn main [] (or (= 1 2) (= 3 3)))")))))

(deftest when-emits-and-desugars-to-if-do-0
  (testing "(when 1 2 3): truthy test -> the do-block's last value (real fixture,
            src/demo_when.kotoba)"
    (let [forms (runtime/read-file "src/demo_when.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm) "when is no longer :unsupported-op")
      (is (= 3 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest when-short-circuits-on-a-falsy-test-without-evaluating-the-body
  (testing "(when 0 (spin 0)): falsy test must skip the never-returning body entirely
            (real fixture, src/demo_when_short_circuit.kotoba) -- proven by completing
            under a tiny fuel budget"
    (let [forms (runtime/read-file "src/demo_when_short_circuit.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 0 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []
                                   {:kotoba.policy/fuel 200}))
          "returns 0 without ever reaching (spin 0)"))))

(deftest when-inline-variant-covers-falsy-test-single-body-form
  (testing "falsy test -> 0, single-form body"
    (is (= 0 (emit-and-run "(ns t)\n(defn main [] (when 0 5))")))))

(deftest short-circuit-fuel-harness-sanity-check
  (testing "the SAME never-returning `spin` call, when actually reached (truthy `and`
            branch instead of falsy), really does trap on fuel exhaustion -- proving
            the short-circuit tests above are meaningful (the harness can and does
            detect a reached infinite call) rather than vacuously passing"
    (let [forms (runtime/read-forms
                 "(ns t)\n(defn spin [x] (spin x))\n(defn main [] (and 1 (spin 0)))"
                 :kotoba)
          wasm (runtime/wasm-binary forms)
          trapped (try
                    (wasm-exec/run-main (:kotoba.wasm/binary wasm) []
                                        {:kotoba.policy/fuel 200})
                    ::did-not-trap
                    (catch clojure.lang.ExceptionInfo e (ex-data e)))]
      (is (:kotoba.wasm/ok? wasm))
      (is (not= ::did-not-trap trapped)
          "and's truthy first arg must actually reach (spin 0)")
      (is (= :fuel-exhausted (:kotoba.wasm/problem trapped))))))
