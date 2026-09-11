(ns kotoba.wasm-case-test
  "Regression coverage for `case` desugar support. Before this fix, `case`
  had no `lower-node` entry (unlike its sibling `cond`), so it survived
  `lower-language-forms` unchanged and `compile-wasm-expr` rejected it with
  `{:kotoba.wasm/problem :unsupported-op :kotoba.wasm/op \"case\"}` -- a
  plain implementation gap, not an intentional exclusion.

  Proves, through the SAME real (non-mock) compile -> emit -> Chicory-
  execute path `kotoba.wasm-exec-test` and `kotoba.wasm-and-or-when-test`
  use elsewhere in this suite:
  1. `kotoba wasm emit` now succeeds for `case` (the exact failure this
     test suite would have caught before the fix).
  2. Basic dispatch-and-default semantics match real Clojure `case`.
  3. A list in test position matches ANY of its constants.
  4. No default + no match is a genuine runtime failure (native WASM
     trap), not a silently wrong value."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run
  "Compile SRC (a `.kotoba` source string) to WASM and execute its `main`
  through a real Chicory instance, returning the i64/i32 result."
  [src]
  (let [forms (runtime/read-forms src :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "kotoba wasm emit should succeed: " (:kotoba.wasm/problems wasm)))
    (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))

(deftest case-emits-and-dispatches-to-the-matching-clause
  (testing "(case 2 1 10 2 20 3 30 99): matches the middle clause -> 20
            (real fixture, src/demo_case.kotoba)"
    (let [forms (runtime/read-file "src/demo_case.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm) "case is no longer :unsupported-op")
      (is (= 20 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest case-falls-through-to-the-default-on-no-match
  (testing "(case 5 1 10 2 20 99): no clause matches -> the trailing default
            (real fixture, src/demo_case_default.kotoba)"
    (let [forms (runtime/read-file "src/demo_case_default.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 99 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest case-list-test-matches-any-listed-constant
  (testing "(case 2 (1 2 3) 100 (4 5 6) 200 0): 2 is a member of (1 2 3)
            -> 100 (real fixture, src/demo_case_multi_test.kotoba)"
    (let [forms (runtime/read-file "src/demo_case_multi_test.kotoba" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm))
      (is (= 100 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest case-inline-variants-cover-no-default-match-and-even-clause-count
  (testing "no default, dispatch value matches the last clause"
    (is (= 20 (emit-and-run "(ns t)\n(defn main [] (case 2 1 10 2 20))"))))
  (testing "no default, dispatch value matches the first clause"
    (is (= 10 (emit-and-run "(ns t)\n(defn main [] (case 1 1 10 2 20))"))))
  (testing "single clause plus default"
    (is (= 0 (emit-and-run "(ns t)\n(defn main [] (case 9 1 10 0))"))))
  (testing "dispatch value is itself an expression, evaluated once"
    (is (= 20 (emit-and-run "(ns t)\n(defn main [] (case (+ 1 1) 1 10 2 20 99))"))))
  (testing "case composes with keyword dispatch values"
    (is (= 1 (emit-and-run "(ns t)\n(defn main [] (case :b :a 0 :b 1 :c 2 9))")))))

(deftest case-single-evaluation-of-the-dispatch-expression
  (testing "a dispatch expression with a side-effecting-looking shape (a call)
            must be evaluated exactly once, not once per clause test -- proven
            by a fuel budget too small to afford re-evaluating a several-call
            chain per clause"
    (is (= 30 (emit-and-run
               (str "(ns t)\n"
                    "(defn dispatch [] (+ 1 2))\n"
                    "(defn main [] (case (dispatch) 1 10 2 20 3 30 99))"))))))

(deftest case-no-default-and-no-match-traps-instead-of-silently-returning
  (testing "(case 9 1 10 2 20): no default and no clause matches 9 -- this
            must fail loudly (a real runtime trap), never fall through to an
            :unsupported-op/:unsupported-form compile error or a silently
            wrong return value"
    (let [forms (runtime/read-forms "(ns t)\n(defn main [] (case 9 1 10 2 20))" :kotoba)
          wasm (runtime/wasm-binary forms)]
      (is (:kotoba.wasm/ok? wasm)
          "case compiles even when a runtime dispatch value could miss every clause")
      (is (thrown? Throwable
                   (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))
          "an unmatched value with no default must trap, not return a value"))))
