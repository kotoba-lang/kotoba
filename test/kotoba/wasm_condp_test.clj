(ns kotoba.wasm-condp-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns condp-test)\n(defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "condp form should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest condp-selects-the-first-match-or-default
  (is (= 20 (emit-and-run "(condp = 2 1 10 2 20 30)")))
  (is (= 30 (emit-and-run "(condp = 3 1 10 2 20 30)")))
  (is (= 9 (emit-and-run "(condp = 1 1 9 99 (quot 1 0) 0)"))
      "a selected clause must short-circuit all later tests"))

(deftest condp-dispatch-is-bound-once
  (let [lowered (runtime/lower-language-forms
                 (runtime/read-forms
                  "(ns once) (defn dispatch [] 2)
                   (defn main [] (condp = (dispatch) 1 10 2 20 30))"
                  :kotoba))]
    (is (= 1 (count (re-seq #"\(dispatch\)" (pr-str lowered)))))))

(deftest condp-without-a-default-traps-on-a-miss
  (is (thrown? Exception
               (emit-and-run "(condp = 3 1 10 2 20)"))))

(deftest condp-validates-its-portable-shape
  (doseq [[source pattern]
          [["(condp)" #"condp requires a predicate and dispatch expression"]
           ["(condp =)" #"condp requires a predicate and dispatch expression"]
           ["(condp (if 1 = =) 1 1 10)"
            #"condp predicate must be an unqualified function symbol"]
           ["(condp qualified/predicate 1 1 10)"
            #"condp predicate must be an unqualified function symbol"]
           ["(condp = 1 1 :>> identity 0)"
            #"condp :>> clauses are not supported by this portable profile"]]]
    (testing source
      (is (thrown-with-msg?
           clojure.lang.ExceptionInfo pattern
           (runtime/lower-language-forms
            (runtime/read-forms (str "(ns bad) (defn main [] " source ")")
                                :kotoba)))))))
