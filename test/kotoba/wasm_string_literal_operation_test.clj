(ns kotoba.wasm-string-literal-operation-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]))

(deftest portable-string-literal-operations-lower-before-tagging
  (testing "concatenation produces one bounded portable literal"
    (is (= ['(main [] "ことば")]
           (runtime/lower-language-forms
            '[(main [] (string-concat "こと" "ば"))]))))
  (testing "substring indexes Unicode code points, not UTF-16 code units"
    (is (= ['(main [] "😀語")]
           (runtime/lower-language-forms
            '[(main [] (string-substring "a😀語z" 1 3))])))))

(deftest portable-string-literal-operations-reject-unrepresentable-cases
  (is (= :dynamic-string-storage-unavailable
         (:reason
          (ex-data
           (try
             (runtime/lower-language-forms
              '[(main [value] (string-concat value "!"))])
             (catch clojure.lang.ExceptionInfo e e))))))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"out of bounds"
       (runtime/lower-language-forms
        '[(main [] (string-substring "abc" 1 4))])))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"exceeds 127 UTF-8 bytes"
       (runtime/lower-language-forms
        (list (list 'main [] (list 'string-concat
                                   (apply str (repeat 127 "a")) "b")))))))
