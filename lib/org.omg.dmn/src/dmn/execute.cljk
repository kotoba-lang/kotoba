(ns dmn.execute
  "A pure evaluator for DMN decision tables over a DRG (Decision Requirements Graph).
  Results are plain EDN — inspectable, replayable, testable offline.

  `evaluate` walks the DRG in topological order (dependencies before dependants),
  merges each dependency's outputs into the context map, then evaluates the target
  decision's table against that enriched context.

  Hit-policy semantics (OMG DMN 1.4 §8.2):
    :unique     — at most one rule may match; returns its output or nil; error data
                  if >1 match
    :first      — first matching rule by row order
    :any        — any matching rule (assumes they all agree); returns first
    :collect    — all matching rules; outputs is a vector of output maps
    :priority   — first matching rule (priority is table-row order here)
    :rule-order — all matching rules in row order; outputs is a vector of output maps"
  (:require [kotoba.lang.text :as str]
            [dmn.model :as m]
            [dmn.ports :as p]))

;; --- internal evaluation helpers ---

(defn- rule->output-map
  "Pair each output column with its then-cell value. Label is preferred over id."
  [outputs rule]
  (zipmap (map #(keyword (or (:dmn/label %) (:dmn/id %))) outputs)
          (:dmn/then rule)))

(defn- eval-inputs
  "Evaluate each input expression against context, returning a positional vector."
  [ports inputs context]
  (mapv (fn [inp] (p/eval-input (:expression ports) (:dmn/expr inp) context))
        inputs))

(defn- match-rule?
  "True iff every when-cell of `rule` is satisfied against the corresponding input value."
  [ports rule input-values]
  (every? true?
          (map (fn [cell v]
                 (boolean (p/eval-cell (:unary ports) (str cell) v)))
               (:dmn/when rule)
               input-values)))

(defn- apply-hit-policy
  "Apply `hit-policy` to `matched` (seq of matching rule maps) and `outputs` columns.
  Returns a map with :dmn/outputs and :dmn/matched (vector of rule ids), or
  :dmn/error/:dmn/multiple-matches for a :unique violation."
  [hit-policy outputs matched]
  (case hit-policy
    :unique
    (cond
      (empty? matched)   {:dmn/outputs nil :dmn/matched []}
      (= 1 (count matched))
      {:dmn/outputs (rule->output-map outputs (first matched))
       :dmn/matched [(:dmn/id (first matched))]}
      :else
      {:dmn/error   :unique/multiple-matches
       :dmn/matched (mapv :dmn/id matched)
       :dmn/outputs nil})

    :first
    (if-let [r (first matched)]
      {:dmn/outputs (rule->output-map outputs r) :dmn/matched [(:dmn/id r)]}
      {:dmn/outputs nil :dmn/matched []})

    :any
    (if-let [r (first matched)]
      {:dmn/outputs (rule->output-map outputs r) :dmn/matched [(:dmn/id r)]}
      {:dmn/outputs nil :dmn/matched []})

    :collect
    {:dmn/outputs (mapv #(rule->output-map outputs %) matched)
     :dmn/matched (mapv :dmn/id matched)}

    :priority
    (if-let [r (first matched)]
      {:dmn/outputs (rule->output-map outputs r) :dmn/matched [(:dmn/id r)]}
      {:dmn/outputs nil :dmn/matched []})

    :rule-order
    {:dmn/outputs (mapv #(rule->output-map outputs %) matched)
     :dmn/matched (mapv :dmn/id matched)}

    ;; unknown
    {:dmn/error :unknown-hit-policy :dmn/hit-policy hit-policy
     :dmn/outputs nil :dmn/matched []}))

(defn- evaluate-one
  "Evaluate a single decision by id against the current context. Returns the
  apply-hit-policy result (does NOT merge outputs into context — caller does that)."
  [ports graph dec-id context]
  (let [dec    (m/decision-by-id graph dec-id)
        ins    (:dmn/inputs dec)
        outs   (:dmn/outputs dec)
        rls    (:dmn/rules dec)
        hp     (:dmn/hit-policy dec)
        iv     (eval-inputs ports ins context)
        matched (filter #(match-rule? ports % iv) rls)]
    (apply-hit-policy hp outs matched)))

(defn- merge-dep-outputs
  "Merge a dependency's :dmn/outputs into ctx. Single-output hit policies
  (:unique/:first/:any/:priority) merge their output map directly.
  Multi-output hit policies (:collect/:rule-order) return a vector of per-rule
  output maps: exactly one matched rule merges its output map directly (same
  as a single-output policy, so downstream rules can compare against it as a
  scalar); more than one matched rule merges each output column as a vector
  of that column's value across all matches, since there is no single scalar
  to hand a downstream rule. Either way, a decision requiring a
  :collect/:rule-order dependency can now see its results instead of the key
  being silently absent from context."
  [ctx outputs]
  (cond
    (map? outputs)
    (merge ctx outputs)

    (and (vector? outputs) (= 1 (count outputs)))
    (merge ctx (first outputs))

    (vector? outputs)
    (reduce (fn [ctx k] (assoc ctx k (mapv #(get % k) outputs)))
            ctx
            (into #{} (mapcat keys) outputs))

    :else ctx))

(defn evaluate
  "Evaluate decision `dec-id` in `graph` against `context` using `ports`.
  Required decisions are evaluated first in topological order, each merging its
  outputs into the context (single-output hit policies merge their output map
  directly; :collect/:rule-order merge each output column as a vector of
  per-matched-rule values). Returns:
    {:dmn/outputs … :dmn/matched [rule-ids] :dmn/context context'}"
  [ports graph dec-id context]
  (let [order (m/topo-order graph dec-id)
        deps  (remove #(= dec-id %) order)
        ;; evaluate dependencies in order, accumulating their outputs into context
        ctx'  (reduce
               (fn [ctx dep-id]
                 (let [res (evaluate-one ports graph dep-id ctx)]
                   (merge-dep-outputs ctx (:dmn/outputs res))))
               context
               deps)
        ;; evaluate the target decision against the enriched context
        result (evaluate-one ports graph dec-id ctx')]
    (assoc result :dmn/context ctx')))

;; --- host-free default ports ---

(defn- parse-number [s]
  #?(:clj  (when (string? s)
              (try (Double/parseDouble s) (catch Exception _ nil)))
     :cljs (when (string? s)
              (let [n (js/parseFloat s)]
                (when-not (js/isNaN n) n)))))

(defn- to-num
  "Coerce x to a number, or return nil."
  [x]
  (if (number? x) x (parse-number (str x))))

(defn- eval-cell-default
  "Pure, portable cell evaluator. Supports:
   - \"-\"         wildcard (always matches)
   - \"a,b,c\"     comma-disjunction (any of)
   - \"[a..b]\"    inclusive range, with (a..b), [a..b), (a..b] variants
   - \"< n\"       comparators: < <= > >= = !=
   - true/false  boolean equality
   - bare number numeric equality
   - bare string string equality (or quoted \"str\")"
  [cell-str input-value]
  (let [s (str/trim (str cell-str))]
    (cond
      ;; wildcard
      (= s "-") true

      ;; comma disjunction: recurse on each segment
      (str/includes? s ",")
      (boolean (some #(eval-cell-default (str/trim %) input-value)
                     (str/split s #",")))

      ;; range: starts with [ or ( and contains ..
      (and (or (str/starts-with? s "[") (str/starts-with? s "("))
           (or (str/ends-with? s "]") (str/ends-with? s ")"))
           (str/includes? s ".."))
      (let [lo-inc (str/starts-with? s "[")
            hi-inc (str/ends-with? s "]")
            inner  (subs s 1 (dec (count s)))
            parts  (str/split inner #"\.\." 2)
            lo     (parse-number (str/trim (first parts)))
            hi     (parse-number (str/trim (second parts)))
            v      (to-num input-value)]
        (boolean (and (some? lo) (some? hi) (some? v)
                      (if lo-inc (<= lo v) (< lo v))
                      (if hi-inc (<= v hi) (< v hi)))))

      ;; comparator: < <= > >= = !=
      (re-find #"^(<=|>=|!=|<|>|=)" s)
      (let [op-len (if (re-find #"^(<=|>=|!=)" s) 2 1)
            op     (subs s 0 op-len)
            num    (parse-number (str/trim (subs s op-len)))
            v      (to-num input-value)]
        (boolean (when (and (some? num) (some? v))
                   (case op
                     "<"  (< v num)
                     "<=" (<= v num)
                     ">"  (> v num)
                     ">=" (>= v num)
                     "="  (== v num)
                     "!=" (not= v num)
                     false))))

      ;; boolean literals
      (= s "true")  (= true input-value)
      (= s "false") (= false input-value)

      ;; numeric literal
      (re-matches #"-?\d+(\.\d+)?" s)
      (let [n (parse-number s)
            v (to-num input-value)]
        (boolean (and (some? n) (some? v) (== n v))))

      ;; quoted string literal
      (and (str/starts-with? s "\"") (str/ends-with? s "\"") (> (count s) 1))
      (= (subs s 1 (dec (count s))) (str input-value))

      ;; bare string equality
      :else (= s (str input-value)))))

(defn default-ports
  "A host-free IExpression + IUnary pair. eval-input looks up (keyword expr) in the
  context map. eval-cell supports wildcards, comparators, ranges, and
  comma-disjunction. Sufficient to exercise full decision-table logic without any
  host; replace with a FEEL engine or custom evaluator for production use."
  []
  {:expression (reify p/IExpression
                 (eval-input [_ expr context]
                   (get context (keyword expr))))
   :unary      (reify p/IUnary
                 (eval-cell [_ cell-str input-value]
                   (eval-cell-default cell-str input-value)))})
