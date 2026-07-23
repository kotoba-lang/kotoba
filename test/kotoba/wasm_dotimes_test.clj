(ns kotoba.wasm-dotimes-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns dotimes-test)\n(defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "dotimes form should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest dotimes-lowers-to-an-executable-fuel-trapped-loop
  (is (= 0 (emit-and-run "(dotimes [i 4] (+ i 1))")))
  (is (= 0 (emit-and-run "(dotimes [i 0] (quot 1 0))"))
      "zero iterations must skip a trapping body")
  (is (= 0 (emit-and-run "(dotimes [i -2] (quot 1 0))"))
      "negative counts also skip the body")
  (is (thrown? Exception
               (emit-and-run "(dotimes [i 4] (if (= i 3) (quot 1 0) 0))"))
      "the loop reaches its final index"))

(deftest dotimes-count-is-bound-once
  (let [lowered (runtime/lower-language-forms
                 (runtime/read-forms
                  "(ns once) (defn limit [] 3) (defn main [] (dotimes [i (limit)] i))"
                  :kotoba))]
    (is (= 1 (count (re-seq #"\(limit\)" (pr-str lowered)))))))

(deftest malformed-dotimes-bindings-fail-during-lowering
  (doseq [source ["(dotimes [i] i)"
                  "(dotimes [i 2 extra] i)"
                  "(dotimes [:i 2] 0)"
                  "(dotimes [qualified/i 2] 0)"]]
    (testing source
      (is (thrown-with-msg?
           clojure.lang.ExceptionInfo #"dotimes requires \[unqualified-symbol count\]"
           (runtime/lower-language-forms
            (runtime/read-forms (str "(ns bad) (defn main [] " source ")") :kotoba)))))))
