(ns kotoba.wasm-string-literal-operation-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(deftest portable-string-literal-operations-lower-before-tagging
  (testing "concatenation produces one bounded portable literal"
    (is (= ['(main [] "ことば")]
           (runtime/lower-language-forms
            '[(main [] (string-concat "こと" "ば"))]))))
  (testing "substring indexes UTF-8 bytes on code-point boundaries"
    (is (= ['(main [] "😀語")]
           (runtime/lower-language-forms
            '[(main [] (string-substring "a😀語z" 1 8))])))))

(defn- emit-and-run [source]
  (let [wasm (runtime/wasm-binary (runtime/read-forms source :kotoba))]
    (is (:kotoba.wasm/ok? wasm) (pr-str (:kotoba.wasm/problems wasm)))
    (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))

(deftest portable-dynamic-string-operations-use-bounded-heap-descriptors
  (is (= 1
         (emit-and-run
          "(ns dynamic.string)
           (defn join [left right] (string-concat left right))
           (defn main []
             (string= (join \"こと\" \"ば\") \"ことば\"))")))
  (is (= 3
         (emit-and-run
          "(ns dynamic.substring)
           (defn choose [value start end]
             (string-substring value start end))
           (defn main []
             (string-length (choose (string-concat \"abc\" \"def\") 1 4)))")))
  (is (= 1
         (emit-and-run
          "(ns dynamic.unicode-substring)
           (defn choose [value start end]
             (string-substring value start end))
           (defn main []
             (string= (choose (string-concat \"a😀\" \"語z\") 1 8)
                      \"😀語\"))"))))

(deftest portable-string-literal-operations-reject-invalid-bounds
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"out of bounds"
       (runtime/lower-language-forms
        '[(main [] (string-substring "abc" 1 4))])))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"exceeds 127 UTF-8 bytes"
       (runtime/lower-language-forms
        (list (list 'main [] (list 'string-concat
                                   (apply str (repeat 127 "a")) "b")))))))

(deftest dynamic-string-operations-trap-on-invalid-bounds
  (is (thrown? Throwable
               (emit-and-run
                "(ns dynamic.invalid-boundary)
                 (defn choose [value start end]
                   (string-substring value start end))
                 (defn main []
                   (string-length (choose (string-concat \"a\" \"😀\") 2 5)))")))
  (is (thrown? Throwable
               (emit-and-run
                (str "(ns dynamic.oversize)"
                     "(defn join [left right] (string-concat left right))"
                     "(defn main [] (string-length (join \""
                     (apply str (repeat 127 "a"))
                     "\" \"b\")))")))))

(deftest dynamic-symbol-construction-shares-quoted-symbol-identity
  (is (= 1
         (emit-and-run
          "(ns dynamic.symbol)
           (defn make-symbol [left right]
             (symbol (string-concat left right)))
           (defn main []
             (= (make-symbol \"koto\" \"ba\") 'kotoba))")))
  (is (= 1
         (emit-and-run
          "(ns dynamic.symbol-predicate)
           (defn main [] (symbol? (symbol \"kotoba\")))"))))
