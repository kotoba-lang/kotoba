(ns text-oracle-cases
  "Shared oracle cases for the kotoba.lang.text twin (JUN-1044).

  Data as code: literals here are read by each runner's own language
  reader. Invisible characters are spelled with real \\uXXXX escapes
  (never adjacent to a hex char, which Basilisp's reader rejects).
  Regexes stay backslash-light. Character-literal arguments are avoided:
  where the twin compares characters (escape's cmap), the runner
  normalizes string keys with `first`, which answers each runner's own
  seq element. `:error` pins refusal messages; `:must-fail` inverts.")

(def cases
  [;; ------------------------------------------------------------ split/join
   {:id :split/basic :op :split :args ["a,b,c" #","] :expect ["a" "b" "c"]}
   {:id :split/limit :op :split :args ["a,b,c" #"," 2] :expect ["a" "b,c"]}
   {:id :split/drop-trailing :op :split :args ["a,b," #","] :expect ["a" "b"]}
   {:id :split/multi-char :op :split :args ["a;;b" #"[;,]+"] :expect ["a" "b"]}
   {:id :join/basic :op :join :args ["," ["a" "b"]] :expect "a,b"}
   {:id :join/nil-elem :op :join :args ["," ["a" nil "b"]] :expect "a,,b"}
   {:id :split-lines/mixed :op :split-lines :args ["a\r\nb\nc"] :expect ["a" "b" "c"]}
   {:id :split-lines/lone-cr :op :split-lines :args ["a\rb"] :expect ["a\rb"]}
   ;; ------------------------------------------------------------ trim
   {:id :trim/basic :op :trim :args ["  a  "] :expect "a"}
   {:id :trim/tabs-newlines :op :trim :args ["\ta\n"] :expect "a"}
   {:id :trim/controls :op :trim :args ["a\t\u001c"] :expect "a"}
   {:id :trim/controls-1f :op :trim :args ["a\u001f"] :expect "a"}
   {:id :trim/nbsp-kept :op :trim :args [" g\u00a0h "] :expect "g\u00a0h"}
   {:id :trim/figure-space-kept :op :trim :args ["\u2007g\u2007"] :expect "\u2007g\u2007"}
   {:id :trim/em-space-trimmed :op :trim :args ["\u2003g\u2003"] :expect "g"}
   {:id :triml/basic :op :triml :args ["  a  "] :expect "a  "}
   {:id :trimr/basic :op :trimr :args ["  a  "] :expect "  a"}
   {:id :trim-newline/basic :op :trim-newline :args ["\n\na\n"] :expect "\n\na"}
   {:id :trim-newline/keeps-spaces :op :trim-newline :args ["  a  "] :expect "  a  "}
   ;; ------------------------------------------------------------ case
   {:id :upper/basic :op :upper :args ["aBc"] :expect "ABC"}
   {:id :lower/basic :op :lower :args ["aBc"] :expect "abc"}
   {:id :ascii-lower/basic :op :ascii-lower :args ["aBcÉ"] :expect "abcÉ"}
   {:id :capitalize/basic :op :capitalize :args ["aBC"] :expect "Abc"}
   ;; ------------------------------------------------------------ predicates/search
   {:id :starts/basic :op :starts-with? :args ["hello" "he"] :expect true}
   {:id :starts/negative :op :starts-with? :args ["hello" "lo"] :expect false}
   {:id :ends/basic :op :ends-with? :args ["hello" "lo"] :expect true}
   {:id :includes/basic :op :includes? :args ["hello" "ll"] :expect true}
   {:id :includes/negative :op :includes? :args ["hello" "xx"] :expect false}
   {:id :index-of/basic :op :index-of :args ["hello" "l"] :expect 2}
   {:id :index-of/missing :op :index-of :args ["hello" "x"] :expect nil}
   {:id :last-index-of/basic :op :last-index-of :args ["hello" "l"] :expect 3}
   {:id :blank/empty :op :blank? :args ["   "] :expect true}
   {:id :blank/nonblank :op :blank? :args [" a "] :expect false}
   ;; ------------------------------------------------------------ transform
   {:id :replace/basic :op :replace :args ["aaa" "a" "b"] :expect "bbb"}
   {:id :replace-first/basic :op :replace-first :args ["aaa" "a" "b"] :expect "baa"}
   {:id :reverse/basic :op :reverse :args ["abc"] :expect "cba"}
   {:id :truncate/plain :op :truncate :args ["hello" 3] :expect "hel"}
   {:id :truncate/ellipsis :op :truncate :args ["hello" 4 "..."] :expect "h..."}
   {:id :pad-left/basic :op :pad-left :args ["a" 3 "0"] :expect "00a"}
   {:id :pad-right/basic :op :pad-right :args ["a" 3 "0"] :expect "a00"}
   {:id :escape/basic :op :escape :args ["a<b&c" {"<" "&lt;" "&" "&amp;"}] :expect "a&lt;b&amp;c" :cmap-keys true}
   {:id :re-quote/basic :op :re-quote :args ["a.b*c"] :expect "a\\.b\\*c"}
   ;; ------------------------------------------------------------ regex
   {:id :re-find/basic :op :re-find :args [#"[0-9]+" "ab12cd"] :expect "12"}
   {:id :re-find/groups :op :re-find :args [#"([0-9]+)x" "ab12x"] :expect ["12x" "12"]}
   {:id :re-find/miss :op :re-find :args [#"[0-9]+" "abcd"] :expect nil}
   {:id :re-matches/basic :op :re-matches :args [#"[0-9]+" "12"] :expect "12"}
   {:id :re-matches/miss :op :re-matches :args [#"[0-9]+" "12a"] :expect nil}
   {:id :re-seq/basic :op :re-seq :args [#"[0-9]+" "a1b22"] :expect ["1" "22"]}
   ;; ------------------------------------------------------------ format
   {:id :format/basic :op :format :args ["%s=%d" "a" 1] :expect "a=1"}
   {:id :format/width :op :format :args ["%5d" 42] :expect "   42"}
   {:id :format/hex :op :format :args ["%x" 255] :expect "ff"}
   {:id :format/float :op :format :args ["%.2f" 1.5] :expect "1.50"}
   {:id :format/percent :op :format :args ["100%%"] :expect "100%"}
   {:id :format/bool :op :format :args ["%b" true] :expect "true"}
   ;; ------------------------------------------------------------ codepoints
   {:id :codepoints/basic :op :codepoints :args ["A日"] :expect [65 26085]}
   {:id :from-codepoints/basic :op :from-codepoints :args [[65 26085]] :expect "A日"}
   {:id :from-codepoints/astral :op :from-codepoints-codes :args [[128512]] :expect [128512]}
   ;; ------------------------------------------------------------ text-kernel oracles
   {:id :segment/basic :op :segment-text :args ["a,b,c" "," 1] :expect "b"}
   {:id :segment/out-of-range :op :segment-text :args ["a,b" "," 5] :expect nil}
   {:id :pad-center/even :op :pad-center-text :args ["a" 4 "0"] :expect "0a00"}
   {:id :trim-text/basic :op :trim-text :args ["  a  "] :expect "a"}
   {:id :blank-text/basic :op :blank-text? :args ["  "] :expect true}])

(def must-fail-cases
  [{:id :must-fail/trim-value :op :trim :args ["  a  "] :expect "a " :must-fail true}
   {:id :must-fail/join-value :op :join :args ["," ["a" "b"]] :expect "a;b" :must-fail true}
   {:id :must-fail/nbsp-removed :op :trim :args [" g\u00a0h "] :expect "gh" :must-fail true}])
