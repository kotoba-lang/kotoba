(ns kotoba.lang.test-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.lang.test :as pt]))

(deftest rng-determinism
  (let [[a r1] (pt/next-long (pt/make-rng 42))
        [b r2] (pt/next-long (pt/make-rng 42))]
    (is (= a b))
    (is (= r1 r2))))

(deftest gen-int-range
  (let [[v _] (pt/gen-int (pt/make-rng 7) 5 5)]
    (is (= 5 v)))
  (dotimes [_ 50]
    (let [[v _] (pt/gen-int (pt/make-rng 1) -3 3)]
      (is (<= -3 v 3)))))

(deftest gen-bool-and-element
  (let [[v _] (pt/gen-bool (pt/make-rng 3))]
    (is (boolean? v)))
  (dotimes [_ 30]
    (let [[v _] (pt/gen-element (pt/make-rng 9) [:a :b :c])]
      (is (#{:a :b :c} v)))))

(deftest gen-string-alphabet-and-length
  (dotimes [_ 20]
    (let [[s _] (pt/gen-string (pt/make-rng 2) 5)]
      (is (<= 0 (count s) 5))
      (is (re-matches #"[a-z0-9]*" s)))))

(deftest quickcheck-passes-a-true-property
  (let [r (pt/quickcheck (fn [x] (= (* x 2) (+ x x)))
                         #(pt/gen-int % -100 100) :seed 42 :runs 100)]
    (is (:pass? r))
    (is (= 100 (:runs r)))))

(deftest quickcheck-finds-and-shrinks-a-counterexample
  (let [r (pt/quickcheck (fn [x] (pos? x)) #(pt/gen-int % -10 10) :seed 1 :runs 200)]
    (is (false? (:pass? r)))
    (is (<= (:smallest r) 0))
    (is (pos? (:shrinks r)))))

(deftest shrink-int-toward-zero
  (is (empty? (pt/shrink-int 0)))
  (is (= 0 (first (pt/shrink-int 7)))))

(deftest assertion-helpers
  (is (true? (pt/are-eq? 1 1)))
  (is (false? (pt/are-eq? 1 2)))
  (is (true? (pt/throws? (fn [] (throw (ex-info "x" {}))))))
  (is (false? (pt/throws? (fn [] 1))))
  (is (true? (pt/throws? (fn [] (throw (ex-info "x" {:k 1})))
                          (fn [e] (= (:k (ex-data e)) 1))))))

(deftest gen-from-spec-primitives
  (let [[i _] (pt/gen-from-spec (pt/make-rng 1) {:type :int})]
    (is (int? i)))
  (let [[s _] (pt/gen-from-spec (pt/make-rng 1) {:type :string})]
    (is (string? s)))
  (let [[k _] (pt/gen-from-spec (pt/make-rng 1) {:type :keyword})]
    (is (keyword? k))))
