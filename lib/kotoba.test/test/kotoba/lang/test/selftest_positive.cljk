(ns kotoba.lang.test.selftest-positive
  "Same purpose/isolation as selftest-negative (see its docstring), but the
  OTHER half of the non-negotiable verification: a normal suite exercising
  deftest/is/testing/are with legitimate assertions, expected to show 0
  failures and 0 errors on both hosts."
  (:require [kotoba.lang.test :as t]))

(t/deftest plain-equality
  (t/is (= 4 (+ 2 2)))
  (t/is (= "ab" (str "a" "b"))))

(t/deftest plain-predicate
  (t/is (pos? 5))
  (t/is (not (neg? 5))))

(t/deftest nested-testing-context
  (t/testing "outer"
    (t/testing "inner"
      (t/is (= 1 1)))
    (t/is true)))

(t/deftest thrown-positive
  (t/is (thrown? #?(:clj ArithmeticException :cljs js/Error)
                 (throw #?(:clj (ArithmeticException. "boom")
                           :cljs (js/Error. "boom"))))))

(t/deftest are-templated
  (t/are [x y] (= x y)
    1 1
    2 2
    (+ 1 2) 3))

(t/deftest are-with-predicate-template
  (t/are [n] (pos? n)
    1
    2
    3))
