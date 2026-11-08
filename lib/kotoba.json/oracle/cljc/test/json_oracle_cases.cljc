(ns json-oracle-cases
  "Shared oracle cases for the kotoba.json twin (JUN-1024).

  Data as code: string literals here are read by each runner's own
  language reader (all three support \\uXXXX), never by an EDN data
  reader, so escape-sensitive inputs stay identical everywhere.
  `:error` is a substring of the refusal message (proven identical on
  bb/nbb/basilisp). `:must-fail` cases carry deliberately wrong
  expectations: the runner inverts them, proving it can fail.")

(def cases
  [;; ------------------------------------------------------------ decode
   {:id :decode/scalars :op :decode
    :in "{\"n\":null,\"t\":true,\"f\":false,\"i\":5,\"neg\":-2,\"whole\":5.0,\"e\":1.5}"
    :expect {"n" nil "t" true "f" false "i" 5 "neg" -2 "whole" 5.0 "e" 1.5}}
   {:id :decode/exp :op :decode :in "[1e3,-2E-2,0.5]" :expect [1000.0 -0.02 0.5]}
   {:id :decode/neg-zero :op :decode :in "-0" :expect 0}
   {:id :decode/max-exact-int :op :decode :in "9007199254740991" :expect 9007199254740991}
   {:id :decode/string-escapes :op :decode
    :in "\"a\\nb\\t\\\"q\\\"\\\\\\/\\b\\f\\r\""
    :expect "a\nb\t\"q\"\\/\b\f\r"}
   {:id :decode/u-escape :op :decode :in "\"\\u65e5\\u0021\"" :expect "日!"}
   {:id :decode/astral-pair :op :decode :in "\"\\uD83D\\uDE00\"" :expect "😀"}
   {:id :decode/empty-string :op :decode :in "\"\"" :expect ""}
   {:id :decode/array :op :decode :in "[1,\"a\",null,true,[2]]" :expect [1 "a" nil true [2]]}
   {:id :decode/empty-colls :op :decode :in "{\"a\":[],\"o\":{}}" :expect {"a" [] "o" {}}}
   {:id :decode/nested :op :decode
    :in "{\"x\":[{\"y\":[1,{\"z\":null}]}]}"
    :expect {"x" [{"y" [1 {"z" nil}]}]}}
   {:id :decode/ws :op :decode :in "  {\r\n\t\"a\" : 1 } " :expect {"a" 1}}
   {:id :decode/empty-object :op :decode :in "{}" :expect {}}
   ;; ------------------------------------------------------------ encode
   {:id :encode/scalars :op :encode :in nil :expect "null"}
   {:id :encode/bools :op :encode :in [true false] :expect "[true,false]"}
   {:id :encode/int :op :encode :in 5 :expect "5"}
   {:id :encode/whole-float :op :encode :in 5.0 :expect "5"}
   {:id :encode/float :op :encode :in 1.5 :expect "1.5"}
   {:id :encode/string-escapes :op :encode :in "a\nb\t\"q\"\\" :expect "\"a\\nb\\t\\\"q\\\"\\\\\""}
   {:id :encode/control-u :op :encode :in "\u0001" :expect "\"\\u0001\""}
   {:id :encode/tab-newline-escaped :op :encode :in "a\tb\nc" :expect "\"a\\tb\\nc\""}
   {:id :encode/keyword-value :op :encode :in :v :expect "\"v\""}
   {:id :encode/sorted-keys :op :encode :in {:bb 2 :a 1} :expect "{\"a\":1,\"bb\":2}"}
   {:id :encode/empty :op :encode :in [{} []] :expect "[{},[]]"}
   {:id :encode/nested :op :encode :in {:a [1 {:b 2}]} :expect "{\"a\":[1,{\"b\":2}]}"}
   {:id :encode/single-key-map :op :encode :in {:k 1} :expect "{\"k\":1}"}
   ;; ------------------------------------------------------------ pretty
   {:id :pretty/single :op :json :in {:a [1]}
    :expect "{\n  \"a\": [\n    1\n  ]\n}"}
   {:id :pretty/empty :op :json :in {} :expect "{}"}
   {:id :pretty/scalar-array :op :json :in [1 "a"] :expect "[\n  1,\n  \"a\"\n]"}
   ;; ------------------------------------------------------------ refusals
   {:id :neg/trailing-array-comma :op :decode :in "[1,]" :error "trailing JSON array comma"}
   {:id :neg/trailing-object-comma :op :decode :in "{\"a\":1,}" :error "trailing JSON object comma"}
   {:id :neg/unterminated-string :op :decode :in "\"abc" :error "unterminated JSON string"}
   {:id :neg/unescaped-control :op :decode :in "\"a\u0001!\"" :error "unescaped JSON control character"}
   {:id :neg/bad-escape :op :decode :in "\"\\x\"" :error "invalid JSON escape"}
   {:id :neg/bad-unicode :op :decode :in "\"\\uZZZZ\"" :error "invalid JSON unicode escape"}
   {:id :neg/lone-high :op :decode :in "\"\\uD800\"" :error "invalid JSON unicode escape"}
   {:id :neg/lone-low :op :decode :in "\"\\uDE00\"" :error "invalid JSON unicode escape"}
   {:id :neg/bad-number-leading-zero :op :decode :in "01" :error "invalid JSON number"}
   {:id :neg/bad-number-double-dot :op :decode :in "1.2.3" :error "invalid JSON number"}
   {:id :neg/bad-number-plus :op :decode :in "+1" :error "invalid JSON value"}
   {:id :neg/bad-number-dot :op :decode :in ".5" :error "invalid JSON value"}
   {:id :neg/trailing-input :op :decode :in "1 2" :error "trailing JSON input"}
   {:id :neg/empty-input :op :decode :in "" :error "invalid JSON value"}
   {:id :neg/non-string-key :op :decode :in "{a:1}" :error "JSON object key must be a string"}
   {:id :neg/missing-colon :op :decode :in "{\"a\" 1}" :error "expected object colon"}
   {:id :neg/bad-token :op :decode :in "truX" :error "invalid JSON token"}
   {:id :neg/unclosed :op :decode :in "{\"a\":[1," :error "invalid JSON value"}])

(def must-fail-cases
  "Deliberately wrong expectations. The runner inverts them: each must
  FAIL as a case to count as a pass, proving the harness detects
  regressions."
  [{:id :must-fail/decode-value :op :decode :in "[1,2]" :expect [1 3] :must-fail true}
   {:id :must-fail/encode-value :op :encode :in {:a 1} :expect "{\"a\":2}" :must-fail true}
   {:id :must-fail/refused-passes :op :decode :in "[1,]" :expect [1] :must-fail true}])
