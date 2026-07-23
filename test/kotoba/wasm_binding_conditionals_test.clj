(ns kotoba.wasm-binding-conditionals-test
  "Executable coverage for single-evaluation `if-let` and `when-let` sugar."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns binding-conditionals)\n(defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "binding conditional should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest if-let-selects-a-branch-and-binds-the-value
  (is (= 9 (emit-and-run "(if-let [x 9] x 0)")))
  (is (= 4 (emit-and-run "(if-let [x 0] 9 4)")))
  (is (= 0 (emit-and-run "(if-let [x 0] 9)"))))

(deftest when-let-supports-one-or-many-body-expressions
  (is (= 2 (emit-and-run "(when-let [x 1] (+ x 1))")))
  (is (= 5 (emit-and-run "(when-let [x 1] (+ x 1) (+ x 4))")))
  (is (= 0 (emit-and-run "(when-let [x 0] (quot 1 0))"))
      "false binding must skip the trapping body"))

(deftest binding-expression-is-evaluated-once
  (is (= 3 (emit-and-run
            "(if-let [x (+ 1 2)] (+ x 0) (quot 1 0))"))))

(deftest malformed-binding-conditionals-fail-during-lowering
  (doseq [source ["(if-let [x] x 0)"
                  "(if-let [x 1])"
                  "(when-let [x 1])"]]
    (testing source
      (is (thrown? clojure.lang.ExceptionInfo
                   (runtime/lower-language-forms
                    (runtime/read-forms
                     (str "(ns bad) (defn main [] " source ")") :kotoba)))))))

(deftest negative-conditionals-lower-and-short-circuit
  (is (= 7 (emit-and-run "(if-not 0 7 (quot 1 0))")))
  (is (= 0 (emit-and-run "(if-not 1 (quot 1 0))")))
  (is (= 9 (emit-and-run "(when-not 0 (+ 1 2) (+ 4 5))")))
  (is (= 0 (emit-and-run "(when-not 1 (quot 1 0))")))
  (doseq [source ["(if-not 1)" "(if-not 1 2 3 4)" "(when-not)"]]
    (is (thrown? clojure.lang.ExceptionInfo
                 (runtime/lower-language-forms
                  (runtime/read-forms
                   (str "(ns bad) (defn main [] " source ")") :kotoba))))))
