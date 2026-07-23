(ns kotoba.wasm-doseq-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
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
                  "(doseq [:x [1]] 0)"
                  "(doseq [qualified/x [1]] 0)"
                  "(doseq [w [0] x [1] y [2] z [3]] (+ w x y z))"]]
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

(deftest doseq-while-stops-all-later-iterations
  (is (= 0
         (emit-and-run
          "(doseq [x [1 2 3] :while (< x 2)]
             (if (= x 2) (quot 1 0) 0))")))
  (is (= 0
         (emit-and-run
          "(doseq [x [1 2 3]
                   :let [y (+ x 10)]
                   :while (< y 12)
                   :when (= x 99)]
             (quot 1 0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1 2 3] :while (< x 3)]
                   (if (= x 2) (quot 1 0) 0))"))))

(deftest doseq-runs-at-the-128-item-vector-bound
  (let [items (str/join " " (range 1 129))]
    (is (= 0
           (emit-and-run
            (str "(doseq [x [" items "] :while (< x 65)]"
                 "  (if (= x 65) (quot 1 0) 0))"))))))

(deftest doseq-supports-two-bounded-cartesian-bindings
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1 2] y [1 2 3]]
                   (if (= x 2)
                     (if (= y 3) (quot 1 0) 0)
                     0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1 2]
                         :let [ys [x]]
                         y ys]
                   (if (= x 2)
                     (if (= y 2) (quot 1 0) 0)
                     0))")))
  (is (= 0
         (emit-and-run
          "(doseq [x [1 2] y [1 2 3] :while (< y 2)]
             (if (= y 2) (quot 1 0) 0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1]
                         y [1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17]]
                   0)"))))

(deftest doseq-supports-explicit-pair-sequence-expressions
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x (list 1 2 3)]
                   (if (= x 3) (quot 1 0) 0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x (rest (list 0 1 2 3))]
                   (if (= x 3) (quot 1 0) 0))")))
  (is (= 0
         (emit-and-run
          "(doseq [x (cons 1 (list 2 3)) :while (< x 3)]
             (if (= x 3) (quot 1 0) 0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x (list 1 2) y [x]]
                   (if (= x 2)
                     (if (= y 2) (quot 1 0) 0)
                     0))")))
  (let [tail (str/join " " (range 1 33))]
    (is (thrown? Exception
                 (emit-and-run
                  (str "(doseq [x (cons 0 (list " tail "))] 0)"))))))

(deftest doseq-supports-three-bounded-cartesian-bindings
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1 2] y [3 4] z [5 6]]
                   (if (= x 2)
                     (if (= y 4)
                       (if (= z 6) (quot 1 0) 0)
                       0)
                     0))")))
  (is (= 0
         (emit-and-run
          "(doseq [x [1 2]
                   y [1 2]
                   z [1 2 3] :while (< z 2)]
             (if (= z 2) (quot 1 0) 0))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1] y [1] z [1 2 3 4 5]]
                   0)"))))

(deftest doseq-resolves-let-bound-pair-sequence-symbols
  (is (thrown? Exception
               (emit-and-run
                "(let [xs (list 1 2 3)
                       alias xs]
                   (doseq [x alias]
                     (if (= x 3) (quot 1 0) 0)))")))
  (is (thrown? Exception
               (emit-and-run
                "(doseq [x [1 2]
                         :let [ys (list x (+ x 10))]
                         y ys]
                   (if (= x 2)
                     (if (= y 12) (quot 1 0) 0)
                     0))")))
  (is (thrown? Exception
               (emit-and-run
                "(let [xs (list 99)]
                   (let [xs [1 2]]
                     (doseq [x xs]
                       (if (= x 2) (quot 1 0) 0))))"))))
