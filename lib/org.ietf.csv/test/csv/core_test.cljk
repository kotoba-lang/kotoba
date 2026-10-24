(ns csv.core-test
  (:require [clojure.test :refer [deftest is testing]]
            [csv.core :as csv]))

;; Every case here is one where `split(",")` returns something plausible and
;; wrong. That is the whole reason this namespace exists, so the tests are
;; organised by the mistake rather than by the function.

(deftest a-quoted-field-may-contain-the-separator
  (is (= [["a" "b,c" "d"]] (csv/read-csv "a,\"b,c\",d")))
  (is (= [["" ""]] (csv/read-csv "\"\",\"\""))))

(deftest a-record-is-not-a-line
  (testing "a quoted field may contain newlines, so split-lines is wrong before it starts"
    (is (= [["a" "line1\nline2" "c"]] (csv/read-csv "a,\"line1\nline2\",c")))
    (is (= 1 (count (csv/read-csv "a,\"1\n2\n3\",c")))
        "three newlines, one record"))
  (testing "which is also why this cannot be a scanning reader"
    (is (= 2 (count (csv/read-csv "h\n\"a\nb\""))))))

(deftest a-quote-inside-quotes-is-doubled
  (is (= [["say \"hi\""]] (csv/read-csv "\"say \"\"hi\"\"\"")))
  (is (= [["\""]] (csv/read-csv "\"\"\"\"")))
  (is (= [["a\"b"]] (csv/read-csv "\"a\"\"b\""))))

(deftest line-endings
  (testing "CRLF parsed as LF leaves a trailing CR on every row's last field,
            which compares unequal to the same string, silently, forever"
    (is (= [["a" "b"] ["c" "d"]] (csv/read-csv "a,b\r\nc,d")))
    (is (= [["a" "b"] ["c" "d"]] (csv/read-csv "a,b\nc,d"))))
  (testing "a lone CR is data, not a line ending"
    (is (= [["a\rb"]] (csv/read-csv "a\rb"))
        "old Mac endings are not RFC 4180, and dropping the character would
         corrupt a field that legitimately holds one"))
  (testing "CR inside quotes always survives"
    (is (= [["a\r\nb"]] (csv/read-csv "\"a\r\nb\"")))))

(deftest a-trailing-newline-is-not-an-empty-record
  (is (= [["a" "b"]] (csv/read-csv "a,b\n")))
  (is (= [["a" "b"]] (csv/read-csv "a,b\r\n")))
  (is (= [["a" "b"] ["c" "d"]] (csv/read-csv "a,b\nc,d\n")))
  (testing "but a trailing separator IS an empty final field"
    (is (= [["a" ""]] (csv/read-csv "a,")))
    (is (= [["a" "" ""]] (csv/read-csv "a,,"))))
  (testing "an empty input is no records"
    (is (= [] (csv/read-csv ""))))
  (testing "but a lone newline is ONE record whose single field is empty"
    (is (= [[""]] (csv/read-csv "\n"))
        "consistent with a-newline being one record: the terminator ends a
         record, it does not decide whether one was there. Treating a lone
         newline as zero records would make the two cases obey different
         rules")))

(deftest nothing-is-guessed-about-types
  (is (= [["007" "1.0" "1e5" "true" ""]]
         (csv/read-csv "007,1.0,1e5,true,"))
      "a zip code keeps its leading zero, a version number stays a string, and
       a caller that knows the schema converts — a parser's guess here is
       unrecoverable")
  (is (every? string? (first (csv/read-csv "1,2,3")))))

(deftest read-maps-distinguishes-absent-from-empty
  (is (= [{"id" "1" "name" "alice"}] (csv/read-maps "id,name\n1,alice")))
  (testing "a short row omits the key rather than inventing a value"
    (is (= [{"a" "1"}] (csv/read-maps "a,b\n1"))
        "`a,,b` has an empty middle field and `a,b` has no third one; a parser
         that flattens them takes the distinction away from every caller"))
  (testing "an empty field is present and empty"
    (is (= [{"a" "1" "b" ""}] (csv/read-maps "a,b\n1,"))))
  (testing "a long row keeps its extras under an index rather than dropping them"
    (is (= [{"a" "1" "b" "2" "2" "3"}] (csv/read-maps "a,b\n1,2,3"))))
  (testing "a header alone yields no rows, and no header yields nothing"
    (is (= [] (csv/read-maps "a,b")))
    (is (= [] (csv/read-maps "")))))

(deftest tsv-is-the-same-grammar-with-another-delimiter
  (is (= [["a" "b"] ["c" "d"]] (csv/read-csv "a\tb\nc\td" {:separator \tab})))
  (is (= [["a,b" "c"]] (csv/read-csv "a,b\tc" {:separator \tab}))
      "a comma is ordinary data in TSV"))

(deftest write-quotes-exactly-when-not-quoting-would-change-the-parse
  (is (= "a,b" (csv/write-csv [["a" "b"]] {:newline "\n"})))
  (is (= "\"a,b\",c" (csv/write-csv [["a,b" "c"]] {:newline "\n"})))
  (is (= "\"say \"\"hi\"\"\"" (csv/write-csv [["say \"hi\""]] {:newline "\n"})))
  (is (= "\"a\nb\"" (csv/write-csv [["a\nb"]] {:newline "\n"}))))

(deftest round-trip
  (doseq [rows [[["a" "b"] ["c" "d"]]
                [["a,b" "c\"d" "e\nf"]]
                [["" "" ""]]
                [["007" "value with spaces"]]
                [["\r"] ["\n"] ["\""]]]]
    (is (= rows (csv/read-csv (csv/write-csv rows)))
        (pr-str rows))))
