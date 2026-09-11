(ns kotoba.wasm-threading-test
  "Executable regression coverage for the `->` and `->>` source sugars."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns threading-test)\n(defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "threading form should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest thread-first-lowers-and-executes
  (testing "list and bare-symbol steps insert the value in first position"
    (is (= 9 (emit-and-run "(-> 5 (+ 1) (* 2) (- 3))")))
    (is (= 1 (emit-and-run "(-> 0 zero?)"))))
  (testing "a form with no steps is the initial value"
    (is (= 7 (emit-and-run "(-> 7)")))))

(deftest thread-last-lowers-and-executes
  (testing "list steps insert the value in final position"
    (is (= 10 (emit-and-run "(->> 5 (* 2) (- 20))"))))
  (testing "a bare-symbol step remains a unary call"
    (is (= 1 (emit-and-run "(->> 0 zero?)"))))
  (testing "a form with no steps is the initial value"
    (is (= 11 (emit-and-run "(->> 11)")))))

(deftest threading-runs-before-other-sugar
  (testing "a `when` step is threaded before `when` itself lowers"
    (is (= 7 (emit-and-run "(-> 5 (when 6) (+ 1))"))))
  (testing "nested threading forms are recursively expanded"
    (is (= 12 (emit-and-run "(-> 5 (+ 1) (->> (* 2)))")))))

(deftest malformed-threading-step-fails-during-lowering
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo
       #"threading step must be a symbol or non-empty list"
       (runtime/lower-language-forms
        (runtime/read-forms "(ns bad) (defn main [] (-> 1 [inc]))" :kotoba)))))

(deftest conditional-thread-last-lowers-and-executes
  (is (= 7 (emit-and-run "(cond->> 3 1 (- 10) 0 (quot 0))")))
  (is (= 3 (emit-and-run "(cond->> 3 0 (quot 0))")))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"cond->> update must be a non-empty call form"
       (runtime/lower-language-forms
        (runtime/read-forms "(ns bad) (defn main [] (cond->> 1 1 :bad))" :kotoba)))))

(deftest named-threading-lowers-and-executes
  (is (= 42 (emit-and-run "(as-> 5 x (+ x 2) (* x 6))")))
  (is (= 5 (emit-and-run "(as-> 5 x)")))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"as-> requires an initial value"
       (runtime/lower-language-forms
        (runtime/read-forms "(ns bad) (defn main [] (as-> 1 :x))" :kotoba)))))
