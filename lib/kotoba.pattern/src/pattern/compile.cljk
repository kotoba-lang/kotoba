(ns pattern.compile
  "Compile a regex-subset string into a `pattern-core` program.

  The program is inert data — `{:code [[op a b] ...] :classes [[lo hi ...] ...]
  :fold bool}` — so it can be printed into a `.kotoba` module as an EDN literal,
  shipped in a resource, or handed to the matcher at runtime. The matcher never
  parses anything.

  This half is host-side on purpose. A build turning `#\"\\d{3}-\\d{4}\"` into a
  program is the same kind of work as turning a `.kotoba` file into an artifact:
  it happens once, before the guest runs, and its output is checked in. Moving
  it into Kotoba is possible and would let a guest accept a pattern at runtime;
  nothing here needs that yet, and the parser would be the only place in the
  library that could reject its input.

  ## The subset, and why it is this subset

  Counted 2026-09-09 over kotoba-lang's browser stack — 308 regex literals in
  213 files:

    +   148   [class] 122   (capture) 102   \\s  93   *  84   ?  74
    \\d  56   |        44   anchor     43   (?i) 38   (?:) 34   .  30
    {n} 12   {n,m}     4    lookahead   3   \\w   1   backreference 0

  So: literals, `.`, character classes with ranges and negation, the escapes
  \\d \\D \\s \\S \\w \\W, groups (capturing and not — both compile the same
  way, since the matcher does not extract text yet), alternation, the greedy
  quantifiers * + ? {n} {n,m}, the anchors ^ $, and a leading (?i).

  REFUSED, by name rather than by silence: lookahead and lookbehind, back
  references, non-greedy quantifiers, and inline flags other than a leading
  (?i). `compile-pattern` throws with the offending construct; a pattern this
  cannot express must not compile to one that means something else."
  (:require [kotoba.lang.text :as str]))

;; --- instruction opcodes (kept in step with pattern_core.kotoba) ----------

(def ^:const op-char 0)
(def ^:const op-class 1)
(def ^:const op-any 2)
(def ^:const op-split 3)
(def ^:const op-jmp 4)
(def ^:const op-match 6)
(def ^:const op-bol 7)
(def ^:const op-eol 8)

(defn- cp
  "The code point of a one-character value. ClojureScript has no character
  type -- `(vec \"ab\")` yields the STRINGS \"a\" and \"b\", and `(int \"a\")` is 0 --
  so this is the portable spelling. Measured 2026-09-09: without it every
  literal in a compiled program was code point 0, and the programs still had
  the right SHAPE, which is exactly the kind of wrong that a structural test
  would have called correct."
  [c]
  #?(:clj (cp c) :cljs (.charCodeAt (str c) 0)))

(defn- fail [why detail]
  (throw (ex-info (str "pattern: " why) {:pattern/refused why :pattern/detail detail})))

;; --- named classes --------------------------------------------------------

(def ^:private digit-ranges [[48 57]])
(def ^:private space-ranges [[9 10] [11 13] [32 32]])
(def ^:private word-ranges [[48 57] [65 90] [95 95] [97 122]])

(defn- escape-ranges
  "The ranges an escape stands for, and whether it is the negated form."
  [c]
  (case c
    \d [digit-ranges false]
    \D [digit-ranges true]
    \s [space-ranges false]
    \S [space-ranges true]
    \w [word-ranges false]
    \W [word-ranges true]
    nil))

(defn- escape-literal [c]
  (case c
    \n 10 \r 13 \t 9 \f 12 \0 0
    (cp c)))

;; --- parsing --------------------------------------------------------------
;;
;; Recursive descent over a character vector. `alt` -> `cat` -> `repeat` ->
;; `atom`. The AST is small enough to be its own documentation:
;;
;;   [:lit cp] [:any] [:class ranges neg?] [:bol] [:eol]
;;   [:cat xs] [:alt xs] [:rep x min max]     max nil = unbounded

(declare parse-alt)

(defn- parse-class
  "A [...] class. Returns [ranges neg? next-index]."
  [cs i]
  (let [neg? (= \^ (nth cs i nil))
        i (if neg? (inc i) i)]
    (loop [i i ranges [] first? true]
      (let [c (nth cs i nil)]
        (cond
          (nil? c) (fail "unterminated character class" (apply str cs))
          (and (= c \]) (not first?)) [ranges neg? (inc i)]
          (= c \\)
          (let [e (nth cs (inc i) nil)]
            (when (nil? e) (fail "trailing backslash in class" (apply str cs)))
            (if-let [[rs rneg?] (escape-ranges e)]
              (do (when rneg?
                    ;; [\D] inside a class would need set subtraction
                    (fail "negated escape inside a character class" (str "\\" e)))
                  (recur (+ i 2) (into ranges rs) false))
              (let [cp (escape-literal e)]
                (if (and (= \- (nth cs (+ i 2) nil)) (not= \] (nth cs (+ i 3) nil)))
                  (let [hi (nth cs (+ i 3) nil)]
                    (recur (+ i 4) (conj ranges [cp (cp hi)]) false))
                  (recur (+ i 2) (conj ranges [cp cp]) false)))))
          ;; a - b, unless the dash is last
          (and (= \- (nth cs (inc i) nil)) (not= \] (nth cs (+ i 2) nil)) (some? (nth cs (+ i 2) nil)))
          (recur (+ i 3) (conj ranges [(cp c) (cp (nth cs (+ i 2)))]) false)
          :else (recur (inc i) (conj ranges [(cp c) (cp c)]) false))))))

(defn- parse-atom [cs i]
  (let [c (nth cs i nil)]
    (cond
      (nil? c) [nil i]
      (= c \() (let [group? (= [\? \:] [(nth cs (inc i) nil) (nth cs (+ i 2) nil)])
                     start (if group? (+ i 3) (inc i))]
                 (when (and (= \? (nth cs (inc i) nil)) (not group?))
                   (fail "only (?: ) and a leading (?i) are admitted"
                         (apply str (take 4 (drop i cs)))))
                 (let [[node j] (parse-alt cs start)]
                   (when-not (= \) (nth cs j nil))
                     (fail "unterminated group" (apply str cs)))
                   [node (inc j)]))
      (= c \[) (let [[ranges neg? j] (parse-class cs (inc i))]
                 [[:class ranges neg?] j])
      (= c \.) [[:any] (inc i)]
      (= c \^) [[:bol] (inc i)]
      (= c \$) [[:eol] (inc i)]
      (= c \\) (let [e (nth cs (inc i) nil)]
                 (when (nil? e) (fail "trailing backslash" (apply str cs)))
                 (when (<= 48 (cp e) 57)
                   (fail "back reference" (str "\\" e)))
                 (if-let [[rs neg?] (escape-ranges e)]
                   [[:class rs neg?] (+ i 2)]
                   [[:lit (escape-literal e)] (+ i 2)]))
      :else [[:lit (cp c)] (inc i)])))

(defn- parse-count [cs i]
  "Parse {n} / {n,} / {n,m} starting after the brace. Returns [min max j]."
  (let [close (loop [j i] (cond (nil? (nth cs j nil)) nil
                                (= \} (nth cs j)) j
                                :else (recur (inc j))))]
    (when-not close (fail "unterminated {n,m}" (apply str cs)))
    (let [body (apply str (subvec cs i close))
          [a b] (str/split body #"," 2)
          lo (parse-long (str/trim a))]
      (when (nil? lo) (fail "unreadable {n,m}" body))
      [lo (cond (nil? b) lo
                (str/blank? b) nil
                :else (parse-long (str/trim b)))
       (inc close)])))

(defn- parse-repeat [cs i]
  (let [[node j] (parse-atom cs i)]
    (if (nil? node)
      [nil j]
      (loop [node node j j]
        (let [c (nth cs j nil)]
          (when (and (#{\* \+ \?} c) (= \? (nth cs (inc j) nil)))
            (fail "non-greedy quantifier" (str c "?")))
          (case c
            \* (recur [:rep node 0 nil] (inc j))
            \+ (recur [:rep node 1 nil] (inc j))
            \? (recur [:rep node 0 1] (inc j))
            \{ (let [[lo hi k] (parse-count cs (inc j))]
                 (recur [:rep node lo hi] k))
            [node j]))))))

(defn- parse-cat [cs i]
  (loop [i i xs []]
    (let [c (nth cs i nil)]
      (if (or (nil? c) (= c \|) (= c \)))
        [(if (= 1 (count xs)) (first xs) [:cat xs]) i]
        (let [[node j] (parse-repeat cs i)]
          (if (nil? node)
            [(if (= 1 (count xs)) (first xs) [:cat xs]) j]
            (recur j (conj xs node))))))))

(defn- parse-alt [cs i]
  (loop [i i branches []]
    (let [[node j] (parse-cat cs i)
          branches (conj branches node)]
      (if (= \| (nth cs j nil))
        (recur (inc j) branches)
        [(if (= 1 (count branches)) (first branches) [:alt branches]) j]))))

;; --- emitting -------------------------------------------------------------
;;
;; Thompson construction. `emit` returns [code classes] where every pc in the
;; code is absolute, so the caller offsets nothing.

(defn- class-index [classes ranges]
  (let [flat (vec (mapcat identity ranges))]
    (if-let [i (first (keep-indexed #(when (= %2 flat) %1) classes))]
      [i classes]
      [(count classes) (conj classes flat)])))

(declare emit)

(defn- emit-seq [xs base classes]
  (reduce (fn [[code classes] x]
            (let [[c2 classes] (emit x (+ base (count code)) classes)]
              [(into code c2) classes]))
          [[] classes] xs))

(defn- emit-rep [node lo hi base classes]
  (cond
    ;; x{0,} -- L: split(L+1, out), x, jmp L
    (and (= lo 0) (nil? hi))
    (let [[body classes] (emit node (+ base 1) classes)
          out (+ base 1 (count body) 1)]
      [(into (into [[op-split (+ base 1) out]] body) [[op-jmp base]]) classes])

    ;; x{1,} -- L: x, split(L, out)
    (and (= lo 1) (nil? hi))
    (let [[body classes] (emit node base classes)
          split-pc (+ base (count body))]
      [(conj body [op-split base (+ split-pc 1)]) classes])

    ;; x{0,1}
    (and (= lo 0) (= hi 1))
    (let [[body classes] (emit node (+ base 1) classes)]
      [(into [[op-split (+ base 1) (+ base 1 (count body))]] body) classes])

    ;; x{n,} -- n copies then x{0,}
    (nil? hi)
    (emit [:cat (conj (vec (repeat lo node)) [:rep node 0 nil])] base classes)

    ;; x{n,m} -- n copies then (m-n) optional copies
    :else
    (do (when (< hi lo) (fail "{n,m} with m < n" (str "{" lo "," hi "}")))
        (emit [:cat (into (vec (repeat lo node))
                          (repeat (- hi lo) [:rep node 0 1]))]
              base classes))))

(defn- emit [node base classes]
  (case (first node)
    :lit [[[op-char (second node)]] classes]
    :any [[[op-any 0]] classes]
    :bol [[[op-bol 0]] classes]
    :eol [[[op-eol 0]] classes]
    :class (let [[idx classes] (class-index classes (second node))]
             [[[op-class idx (if (nth node 2) 1 0)]] classes])
    :cat (emit-seq (second node) base classes)
    :rep (emit-rep (second node) (nth node 2) (nth node 3) base classes)
    :alt (let [branches (second node)]
           (if (= 1 (count branches))
             (emit (first branches) base classes)
             ;; split(branch, rest) branch jmp(end) rest...
             (let [[b classes] (emit (first branches) (+ base 1) classes)
                   after (+ base 1 (count b) 1)
                   [rest-code classes] (emit [:alt (vec (rest branches))] after classes)
                   end (+ after (count rest-code))]
               [(-> [[op-split (+ base 1) after]]
                    (into b)
                    (into [[op-jmp end]])
                    (into rest-code))
                classes])))))

(defn compile-pattern
  "regex-subset string -> a `pattern-core` program (plain data)."
  [re]
  (let [fold? (str/starts-with? re "(?i)")
        re (if fold? (subs re 4) re)]
    (when (str/includes? re "(?=") (fail "lookahead" re))
    (when (str/includes? re "(?!") (fail "negative lookahead" re))
    (when (str/includes? re "(?<") (fail "lookbehind" re))
    (when (re-find #"\(\?[^:]" re) (fail "inline flags other than a leading (?i)" re))
    (let [cs (vec re)
          [ast i] (parse-alt cs 0)]
      (when (not= i (count cs)) (fail "unparsed input" (subs re i)))
      (let [[code classes] (emit (or ast [:cat []]) 0 [])]
        {:code (conj (vec code) [op-match 0])
         :classes (vec classes)
         :fold fold?}))))

(defn program-edn
  "The program as EDN text, the form a `.kotoba` module embeds."
  [re]
  (pr-str (compile-pattern re)))
