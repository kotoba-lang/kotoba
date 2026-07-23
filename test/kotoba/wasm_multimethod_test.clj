(ns kotoba.wasm-multimethod-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- emit-and-run [forms]
  (let [source (str "(ns multimethod-test)\n" forms)
        read-forms (runtime/read-forms source :kotoba)
        wasm (runtime/wasm-binary read-forms)]
    (is (:kotoba.wasm/ok? wasm)
        (str "multimethod forms should emit: " (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))

(deftest closed-multimethod-dispatches-and-defaults
  (let [prefix "(defn kind [x] x)
                (defmulti render kind)
                (defmethod render 1 [x] (+ x 10))
                (defmethod render 2 [x] (+ x 20))
                (defmethod render :default [x] 99)"]
    (is (= 11 (emit-and-run (str prefix " (defn main [] (render 1))"))))
    (is (= 22 (emit-and-run (str prefix " (defn main [] (render 2))"))))
    (is (= 99 (emit-and-run (str prefix " (defn main [] (render 7))"))))))

(deftest defmethod-order-is-declaration-independent
  (is (= 12
         (emit-and-run
          "(defmethod render 2 [x] (+ x 10))
           (defn kind [x] x)
           (defmulti render kind)
           (defmethod render 1 [x] 0)
           (defn main [] (render 2))"))))

(deftest closed-multimethod-without-default-traps-on-a-miss
  (is (thrown? Exception
               (emit-and-run
                "(defn kind [x] x)
                 (defmulti render kind)
                 (defmethod render 1 [x] 10)
                 (defn main [] (render 2))"))))

(deftest closed-multimethod-validates-static-shapes
  (doseq [[source pattern]
          [["(defn kind [x] x) (defmulti render (fn [x] x))
             (defmethod render 1 [x] x) (defn main [] 0)"
            #"defmulti requires an unqualified name"]
           ["(defn kind [x] x) (defmulti render kind)
             (defmethod render 1 [x] x) (defmethod render 1 [x] x)
             (defn main [] 0)"
            #"duplicate defmethod dispatch value"]
           ["(defn kind [x] x) (defmulti render kind)
             (defmethod render 1 [x] x) (defmethod render 2 [y] y)
             (defn main [] 0)"
            #"all defmethods must use the same parameter vector"]
           ["(defmethod render 1 [x] x) (defn main [] 0)"
            #"defmethod requires a matching defmulti declaration"]]]
    (testing source
      (is (thrown-with-msg?
           clojure.lang.ExceptionInfo pattern
           (runtime/lower-language-forms
            (runtime/read-forms (str "(ns bad) " source) :kotoba)))))))
