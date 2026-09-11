(ns kotoba.wasm-some-sugar-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [body]
  (let [forms (runtime/read-forms
               (str "(ns some-sugar) (defn add-some [x] (+ x 1)) "
                    "(defn add-last [n x] (+ n x)) (defn main [] " body ")")
               :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm) (pr-str (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest option-presence-bindings-use-the-i64-absence-model
  (is (= 9 (emit-and-run "(if-some [x 9] x 4)")))
  (is (= 4 (emit-and-run "(if-some [x 0] 9 4)")))
  (is (= 6 (emit-and-run "(when-some [x 2] (+ x 1) (+ x 4))"))))

(deftest some-threading-short-circuits-and-inserts-in-the-right-position
  (is (= 7 (emit-and-run "(some-> 5 add-some add-some)")))
  (is (= 14 (emit-and-run "(some->> 5 (add-last 9))")))
  (is (= 0 (emit-and-run "(some-> 0 (quot 0))"))
      "an absent initial value must skip the trapping step"))

(deftest malformed-some-sugar-fails-during-lowering
  (doseq [source ["(if-some [x] x 0)" "(when-some [x 1])"
                  "(some-> 1 [inc])"]]
    (testing source
      (is (thrown? clojure.lang.ExceptionInfo
                   (runtime/lower-language-forms
                    (runtime/read-forms
                     (str "(ns bad) (defn main [] " source ")") :kotoba)))))))
