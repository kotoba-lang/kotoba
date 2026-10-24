(ns sigma.execute
  "Pure Sigma rule evaluator. matches? tests an event map against a compiled
  rule using host-injected field extraction (sigma.ports/IField). No I/O.

  Condition expression supports:
    identifier      — named selection must match
    not expr        — negation
    expr and expr   — conjunction
    expr or expr    — disjunction
    ( expr )        — grouping
    1 of <glob>     — any selection whose name matches the glob pattern
    all of them     — every defined selection must match
    all of <glob>   — every selection matching the glob must match

  Selection matching:
    Every field-criterion in a selection must match (AND over fields).
    A field-criterion with a list of values is OR over those values by default;
    the |all modifier switches it to AND (all values must match).

  Modifiers:
    contains    — field value (as string) contains the criterion string
    startswith  — field value starts with the criterion string
    endswith    — field value ends with the criterion string
    re          — re-find match of criterion as a regex against the field value
    gt          — field value (numeric) is greater than the criterion (numeric)
    lt          — field value (numeric) is less than the criterion (numeric)
    all         — AND over values instead of OR (logic modifier)"
  (:require [kotoba.lang.text :as str]
            [sigma.model :as m]
            [sigma.ports :as p]))

;; --- numeric coercion ---

(defn- parse-num [s]
  #?(:clj  (when (string? s)
              (try (Double/parseDouble s) (catch Exception _ nil)))
     :cljs (when (string? s)
              (let [n (js/parseFloat s)]
                (when-not (js/isNaN n) n)))))

;; --- single-value criterion test ---

(defn- criterion-matches?
  "Test whether one criterion value `crit-val` matches `field-val` using `data-mod`.
  `data-mod` is nil (exact equality) or one of contains/startswith/endswith/re/gt/lt."
  [data-mod field-val crit-val]
  (let [sv (str field-val)
        sc (str crit-val)]
    (case data-mod
      "contains"   (str/includes? sv sc)
      "startswith" (str/starts-with? sv sc)
      "endswith"   (str/ends-with? sv sc)
      "re"         (boolean (re-find (re-pattern sc) sv))
      "gt"         (let [fv (parse-num sv) cv (parse-num sc)]
                     (boolean (and fv cv (> fv cv))))
      "lt"         (let [fv (parse-num sv) cv (parse-num sc)]
                     (boolean (and fv cv (< fv cv))))
      ;; no data modifier: exact string equality
      (= sv sc))))

;; --- field-criterion list test ---

(defn- field-criterion-matches?
  "Test whether `field-val` satisfies the `values` list under `modifiers`.
  OR over values by default; AND when |all modifier is present."
  [modifiers field-val values]
  (let [all?     (boolean (some #{"all"} modifiers))
        data-mod (first (filter #{"contains" "startswith" "endswith" "re" "gt" "lt"}
                                modifiers))
        test-one (fn [cv] (criterion-matches? data-mod field-val cv))]
    (if all?
      (every? test-one values)
      (boolean (some test-one values)))))

;; --- selection compilation ---

(defn- parse-field-key
  "Split \"User|contains|all\" into {:field \"User\" :modifiers [\"contains\" \"all\"]}."
  [field-key]
  (let [parts (str/split field-key #"\|")]
    {:field     (first parts)
     :modifiers (vec (rest parts))}))

(defn- compile-selection
  "Return a function [ports event] -> boolean for one named selection map.
  A selection matches iff every field-criterion matches (AND over fields)."
  [sel-map]
  (fn [ports event]
    (every? (fn [[field-key values]]
              (let [{:keys [field modifiers]} (parse-field-key field-key)
                    field-val (p/extract (:field ports) field event)]
                (field-criterion-matches? modifiers field-val values)))
            sel-map)))

;; --- condition parser (recursive-descent, letfn for mutual recursion) ---

(defn- tokenize [s]
  (vec (re-seq #"[^\s()]+|[()]" s)))

(defn- parse-condition
  "Parse condition string `s` into an AST map.
  AST node types: :ref :not :and :or :1-of :all-of-glob :all-of-them"
  [s]
  (letfn [(parse-atom [tokens]
            (let [tok (first tokens)
                  rst (rest tokens)]
              (cond
                (= tok "(")
                (let [[inner rest1] (parse-or rst)]
                  (if (= (first rest1) ")")
                    [inner (rest rest1)]
                    [inner rest1]))

                (= tok "1")
                (if (= (second tokens) "of")
                  (let [glob (nth tokens 2 nil)]
                    [{:type :1-of :glob glob} (drop 3 tokens)])
                  [{:type :ref :name tok} rst])

                (= tok "all")
                (if (= (second tokens) "of")
                  (let [pat (nth tokens 2 nil)]
                    (if (= pat "them")
                      [{:type :all-of-them} (drop 3 tokens)]
                      [{:type :all-of-glob :glob pat} (drop 3 tokens)]))
                  [{:type :ref :name tok} rst])

                (some? tok)
                [{:type :ref :name tok} rst]

                :else
                [nil tokens])))

          (parse-not [tokens]
            (if (= (first tokens) "not")
              (let [[child rest1] (parse-not (rest tokens))]
                [{:type :not :child child} rest1])
              (parse-atom tokens)))

          (parse-and [tokens]
            (let [[left rest1] (parse-not tokens)]
              (loop [left left tokens rest1]
                (if (= (first tokens) "and")
                  (let [[right rest2] (parse-not (rest tokens))]
                    (recur {:type :and :left left :right right} rest2))
                  [left tokens]))))

          (parse-or [tokens]
            (let [[left rest1] (parse-and tokens)]
              (loop [left left tokens rest1]
                (if (= (first tokens) "or")
                  (let [[right rest2] (parse-and (rest tokens))]
                    (recur {:type :or :left left :right right} rest2))
                  [left tokens]))))]
    (first (parse-or (tokenize s)))))

;; --- glob matching ---

(defn- glob-matches?
  "True if glob pattern (using * as wildcard) matches sel-name."
  [glob sel-name]
  (let [escaped (-> glob
                    (str/replace "\\" "\\\\")
                    (str/replace "." "\\.")
                    (str/replace "+" "\\+")
                    (str/replace "?" "\\?")
                    (str/replace "^" "\\^")
                    (str/replace "$" "\\$")
                    (str/replace "|" "\\|")
                    (str/replace "(" "\\(")
                    (str/replace ")" "\\)")
                    (str/replace "[" "\\[")
                    (str/replace "]" "\\]")
                    (str/replace "*" ".*"))]
    (boolean (re-matches (re-pattern (str "^" escaped "$")) sel-name))))

;; --- condition evaluation ---

(defn- eval-condition
  "Evaluate AST against sel-fns (map of name -> [ports event] -> boolean)."
  [ast sel-fns ports event]
  (when ast
    (case (:type ast)
      :ref
      (if-let [f (get sel-fns (:name ast))]
        (f ports event)
        false)

      :not
      (not (eval-condition (:child ast) sel-fns ports event))

      :and
      (and (eval-condition (:left ast) sel-fns ports event)
           (eval-condition (:right ast) sel-fns ports event))

      :or
      (or (eval-condition (:left ast) sel-fns ports event)
          (eval-condition (:right ast) sel-fns ports event))

      :1-of
      (boolean (some (fn [[sel-name f]]
                       (when (glob-matches? (:glob ast) sel-name)
                         (f ports event)))
                     sel-fns))

      :all-of-glob
      (let [matching (filter (fn [[sel-name _]]
                               (glob-matches? (:glob ast) sel-name))
                             sel-fns)]
        (and (seq matching)
             (every? (fn [[_ f]] (f ports event)) matching)))

      :all-of-them
      (and (seq sel-fns)
           (every? (fn [[_ f]] (f ports event)) sel-fns))

      false)))

;; --- public API ---

(defn matches?
  "Return true iff `event` matches the Sigma `rule` using host `ports`.
  Compiles each named selection to a predicate, then evaluates the
  condition expression (and/or/not/quantifiers) against them."
  [ports rule event]
  (let [sels    (m/selections rule)
        sel-fns (reduce-kv (fn [acc k v]
                             (assoc acc k (compile-selection v)))
                           {}
                           sels)
        ast     (parse-condition (m/condition rule))]
    (boolean (eval-condition ast sel-fns ports event))))
