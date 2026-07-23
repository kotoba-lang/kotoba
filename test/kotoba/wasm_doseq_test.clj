(ns kotoba.wasm-doseq-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns doseq-test)\n(defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "doseq form should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest doseq-walks-the-pair-chain-and-returns-zero
  (is (= 0 (emit-and-run "(doseq [x [1 2 3]] (+ x 10))")))
  (is (= 0 (emit-and-run "(doseq [x []] (quot 1 0))"))
      "an empty collection must skip the body")
  (is (thrown? Exception
               (emit-and-run "(doseq [x [1 2 3]]
                                (if (= x 3) (quot 1 0) 0))"))
      "the loop must reach the final element"))

(deftest doseq-collection-is-bound-once
  (let [lowered (runtime/lower-language-forms
                 (runtime/read-forms
                  "(ns once) (defn item [] 3)
                   (defn main [] (doseq [x [1 2 (item)]] x))"
                  :kotoba))]
    (is (= 1 (count (re-seq #"\(item\)" (pr-str lowered)))))))

(deftest doseq-validates-its-bounded-binding-shape
  (doseq [source ["(doseq [x] x)"
                  "(doseq [x [1] y [2]] (+ x y))"
                  "(doseq [:x [1]] 0)"
                  "(doseq [qualified/x [1]] 0)"
                  "(doseq [x [1] :while x] x)"]]
    (testing source
      (is (thrown?
           clojure.lang.ExceptionInfo
           (runtime/lower-language-forms
           (runtime/read-forms (str "(ns bad) (defn main [] " source ")")
                                :kotoba)))))))

(deftest doseq-admits-dynamic-bounded-vector-expressions
  (is (= 0
         (emit-and-run
          "(let [xs (if 1 [1 2 3] [])]
             (doseq [x xs] (+ x 1)))")))
  (is (thrown? Exception
               (emit-and-run
                "(let [xs (if 1 [1 2 3] [])]
                   (doseq [x xs]
                     (if (= x 3) (quot 1 0) 0)))"))))

(deftest doseq-supports-ordered-let-and-when-modifiers
  (is (= 0
         (emit-and-run
          "(doseq [x [1 2 3] :let [y (+ x 10)] :when (= y 99)]
             (quot 1 0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1 2 3] :let [y (+ x 10)] :when (= y 12)]
                   (quot 1 0))"))))
