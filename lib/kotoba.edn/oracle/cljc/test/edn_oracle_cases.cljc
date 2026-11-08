(ns edn-oracle-cases
  "Shared oracle cases for the kotoba.lang.edn twin (JUN-1023).

  Data as code: literals here are read by each runner's own language
  reader. `:error` is a substring of the refusal message (identical on
  bb/nbb/basilisp). Character literals read to one-character STRINGS in
  the twin (host-:cljs reading); `:expect-codes` pins code points where a
  literal cannot spell the value. `:must-fail` cases carry deliberately
  wrong expectations; the runner inverts them.")

(def cases
  [;; ------------------------------------------------------------ read-string: scalars
   {:id :read/nil :op :read-string :in "nil" :expect nil}
   {:id :read/bools :op :read-string :in "[true false]" :expect [true false]}
   {:id :read/int :op :read-string :in "42" :expect 42}
   {:id :read/neg :op :read-string :in "-7" :expect -7}
   {:id :read/plus :op :read-string :in "+7" :expect 7}
   {:id :read/float :op :read-string :in "1.5" :expect 1.5}
   {:id :read/exp :op :read-string :in "1e3" :expect 1000.0}
   {:id :read/max-exact :op :read-string :in "9007199254740991" :expect 9007199254740991}
   {:id :read/string :op :read-string :in "\"a\\nb\\t\\\"q\\\"\\\\\\/\\b\\f\\r\"" :expect "a\nb\t\"q\"\\/\b\f\r"}
   {:id :read/string-u :op :read-string :in "\"\\u65e5!\"" :expect "日!"}
   {:id :read/keyword :op :read-string :in ":ns/kw" :expect :ns/kw}
   {:id :read/symbol :op :read-string :in "sym-1" :expect 'sym-1}
   {:id :read/leading-dot-symbol :op :read-string :in ".5" :expect '.5}
   {:id :read/char-a :op :read-string :in "\\a" :expect "a"}
   {:id :read/char-newline :op :read-string :in "\\newline" :expect "\n"}
   {:id :read/char-u :op :read-string :in "\\u65e5" :expect "日"}
   {:id :read/char-lone-codes :op :read-string :in "\\uD800" :expect-codes [55296]}
   ;; ------------------------------------------------------------ collections
   {:id :read/list :op :read-string :in "(1 :a)" :expect '(1 :a)}
   {:id :read/vector :op :read-string :in "[1 [2]]" :expect [1 [2]]}
   {:id :read/map :op :read-string :in "{:a 1 \"s\" [2]}" :expect {:a 1 "s" [2]}}
   {:id :read/set :op :read-string :in "#{:a 1}" :expect #{:a 1}}
   {:id :read/namespaced-map :op :read-string :in "#:ns{:a 1 :b/x 2}" :expect {:ns/a 1 :b/x 2}}
   {:id :read/ws-comments :op :read-string :in "  ; hi\n [1] ; tail\n" :expect [1]}
   ;; ------------------------------------------------------------ tags & opts
   {:id :read/tag-readers :op :read-string :opts {:readers {'inst (fn [v] [:inst v])}}
    :in "#inst \"x\"" :expect [:inst "x"]}
   {:id :read/tag-default :op :read-string :opts {:default (fn [t v] [:d t v])}
    :in "#foo 1" :expect [:d 'foo 1]}
   {:id :read/tag-no-handler :op :read-string :opts {:readers {'inst (fn [v] v)}}
    :in "#foo 1" :error "EDN tagged literal has no reader"}
   {:id :read/tag-strict :op :read-string :in "#inst \"x\"" :error "EDN dispatch forms are forbidden"}
   {:id :read/eof-empty :op :read-string :opts {:eof :eof} :in "" :expect :eof}
   {:id :read/eof-blank :op :read-string :opts {:eof :eof} :in "  ; c\n" :expect :eof}
   {:id :read/eof-with-form :op :read-string :opts {:eof :eof} :in "1" :expect 1}
   {:id :read/unknown-opt :op :read-string :opts {:bogus 1} :in "1" :error "EDN option is not recognised"}
   {:id :read/bad-readers-opt :op :read-string :opts {:readers [:not-a-map]} :in "1" :error "EDN :readers must be a map"}
   {:id :read/bad-default-opt :op :read-string :opts {:default 42} :in "1" :error "EDN :default must be a function"}
   ;; ------------------------------------------------------------ refusals
   {:id :neg/bigint-suffix :op :read-string :in "1N" :error "EDN number would not mean the same"}
   {:id :neg/ratio :op :read-string :in "1/2" :error "EDN number would not mean the same"}
   {:id :neg/bigdec :op :read-string :in "1.5M" :error "EDN number would not mean the same"}
   {:id :neg/big-int :op :read-string :in "9007199254740992" :error "EDN number would not mean the same"}
   {:id :neg/bad-number :op :read-string :in "1.2.3" :error "EDN number is malformed"}
   {:id :neg/dup-key :op :read-string :in "{:a 1 :a 2}" :error "EDN map has a duplicate key"}
   {:id :neg/odd-map :op :read-string :in "{:a 1 :b}" :error "EDN map has an odd number of forms"}
   {:id :neg/dup-set :op :read-string :in "#{:a :a}" :error "EDN set has a duplicate element"}
   {:id :neg/trailing :op :read-string :in "1 2" :error "EDN input contains trailing forms"}
   {:id :neg/empty :op :read-string :in "" :error "EDN input is empty"}
   {:id :neg/dispatch :op :read-string :in "#foo 1" :error "EDN dispatch forms are forbidden"}
   {:id :neg/ns-underscore :op :read-string :in "#:_ {:a 1}" :error "EDN dispatch forms are forbidden"}
   {:id :neg/auto-keyword :op :read-string :in "::a" :error "EDN auto-resolved keywords are forbidden"}
   {:id :neg/empty-keyword :op :read-string :in ":" :error "EDN keyword is empty"}
   {:id :neg/bad-char :op :read-string :in "\\toolongname" :error "EDN character literal is not recognised"}
   {:id :neg/bad-unicode :op :read-string :in "\"\\uZZZZ\"" :error "EDN unicode escape is malformed"}
   {:id :neg/bad-escape :op :read-string :in "\"\\x\"" :error "EDN string escape is not recognised"}
   {:id :neg/unterminated-string :op :read-string :in "\"abc" :error "EDN string is unterminated"}
   {:id :neg/unterminated-coll :op :read-string :in "[1," :error "EDN collection is unterminated"}
   {:id :neg/mismatch :op :read-string :in "[1}" :error "EDN collection delimiters do not match"}
   {:id :neg/depth-limit :op :read-string :in "[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]" :error "EDN nesting exceeds limit"}
   {:id :read/depth-ok :op :read-string :in "[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[\"x\"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]" :expect [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["x"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]}
   {:id :neg/not-text :op :read-string :in 42 :error "EDN input must be text"}
   ;; ------------------------------------------------------------ read-all
   {:id :all/multi :op :read-all :in "1 [2] {:a 1}" :expect [1 [2] {:a 1}]}
   {:id :all/empty :op :read-all :in "" :expect []}
   {:id :all/blank :op :read-all :in "  ; only a comment\n" :expect []}
   {:id :all/eof-refused :op :read-all :opts {:eof :eof} :in "1" :error "EDN :eof has no meaning for read-all"}
   {:id :all/tagged :op :read-all :opts {:readers {'inst (fn [v] [:inst v])}} :in "#inst \"a\" #inst \"b\"" :expect [[:inst "a"] [:inst "b"]]}
   ;; ------------------------------------------------------------ write-string
   {:id :write/scalars :op :write-string :in [1 "a" :k true nil] :expect "[1 \"a\" :k true nil]"}
   {:id :write/single-key :op :write-string :in {:k 1} :expect "{:k 1}"}
   ;; ------------------------------------------------------------ escape-controls
   {:id :esc/keeps-ws :op :escape-controls :in "a\tb\nc\rd" :expect "a\tb\nc\rd"}
   {:id :esc/control :op :escape-controls :in "a\u0001!" :expect "a\\u0001!"}
   {:id :esc/del :op :escape-controls :in "a\u007f!" :expect "a\\u007f!"}
   {:id :esc/idempotent :op :escape-controls :in "a\\u0001b" :expect "a\\u0001b"}])

(def must-fail-cases
  [{:id :must-fail/read-value :op :read-string :in "[1,2]" :expect [1 3] :must-fail true}
   {:id :must-fail/write-value :op :write-string :in {:a 1} :expect "{:a 2}" :must-fail true}
   {:id :must-fail/refused-passes :op :read-string :in "1 2" :expect [1 2] :must-fail true}])
