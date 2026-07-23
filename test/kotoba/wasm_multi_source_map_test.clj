(ns kotoba.wasm-multi-source-map-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [source]
  (let [wasm (runtime/wasm-binary (runtime/read-forms source :kotoba))]
    (is (:kotoba.wasm/ok? wasm) (pr-str (:kotoba.wasm/problems wasm)))
    (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))

(deftest multi-source-map-walks-beyond-the-legacy-eight-item-unroll
  (let [left (pr-str (vec (range 20)))
        right (pr-str (vec (range 20 40)))]
    (is (= 58
           (emit-and-run
            (str "(ns multi.map)"
                 "(defn add [a b] (+ a b))"
                 "(defn main [] (nth (map add "
                 left " " right ") 19 0))"))))))

(deftest multi-source-map-stops-at-the-shortest-input
  (is (= 99
         (emit-and-run
          "(ns multi.shortest)
           (defn add [a b] (+ a b))
           (defn main [] (nth (map add [1 2 3] [10]) 1 99))"))))
