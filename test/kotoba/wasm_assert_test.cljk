(ns kotoba.wasm-assert-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns assert-test)\n(defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "assert form should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest assert-returns-zero-on-success-and-traps-on-failure
  (is (= 0 (emit-and-run "(assert 1)")))
  (is (thrown? Exception (emit-and-run "(assert 0)"))))

(deftest assert-condition-is-lowered-once
  (let [lowered (runtime/lower-language-forms
                 (runtime/read-forms
                  "(ns once) (defn condition [] 1)
                   (defn main [] (assert (condition)))"
                  :kotoba))]
    (is (= 1 (count (re-seq #"\(condition\)" (pr-str lowered)))))))

(deftest assert-rejects-unsupported-arities-and-messages
  (doseq [source ["(assert)" "(assert 1 \"message\")"]]
    (is (thrown-with-msg?
         clojure.lang.ExceptionInfo
         #"assert requires exactly one condition; messages are not supported"
         (runtime/lower-language-forms
          (runtime/read-forms (str "(ns bad) (defn main [] " source ")")
                              :kotoba))))))
