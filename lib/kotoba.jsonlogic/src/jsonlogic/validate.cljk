(ns jsonlogic.validate
  "Structural validation of a JSONLogic rule tree. Pure: returns a vector of
  problem maps `{:jsonlogic/severity :error|:warn :jsonlogic/code … :jsonlogic/id …
  :jsonlogic/msg …}` so a caller decides how to surface them. `valid?` is true iff
  there are no :error-level problems (warnings are advisory).

  Unknown operators produce :warn — they may be handled by custom ports. Obvious
  arity violations (e.g. \"var\" with >2 args, binary ops with wrong count) produce :warn.")

(def ^:private known-ops
  #{"var" "missing" "missing_some"
    "==" "===" "!=" "!==" "!" "!!"
    "and" "or" "if" "?:"
    ">" ">=" "<" "<="
    "+" "-" "*" "/" "%"
    "min" "max"
    "in" "cat" "substr"
    "merge" "map" "filter" "reduce"
    "all" "some" "none"})

(defn- problem [severity code id msg]
  {:jsonlogic/severity severity :jsonlogic/code code :jsonlogic/id id :jsonlogic/msg msg})

(defn- validate-node
  "Recursively validate `rule` rooted at `path`. Returns a seq of problem maps."
  [rule path]
  (cond
    ;; non-map literals are always valid
    (not (map? rule)) []

    ;; empty map — unusual but not an error
    (empty? rule) []

    ;; operation object: exactly one key
    (= 1 (count rule))
    (let [[op args] (first rule)
          id        (str path "/" op)
          self      (cond-> []
                      (not (contains? known-ops op))
                      (conj (problem :warn :op/unknown id
                                     (str "unknown operator \"" op
                                          "\"; will be dispatched to custom ports or throw")))
                      (and (= op "var") (vector? args) (> (count args) 2))
                      (conj (problem :warn :op/arity id
                                     (str "\"var\" expects 1-2 args, got " (count args))))
                      (and (contains? #{"==" "===" "!=" "!==" ">" ">=" "<" "<="} op)
                           (vector? args)
                           (not (contains? #{2 3} (count args))))
                      (conj (problem :warn :op/arity id
                                     (str "\"" op "\" expects 2 args (or 3 for between), got "
                                          (count args)))))
          children  (if (vector? args)
                      (vec (mapcat (fn [i child]
                                     (validate-node child (str id "[" i "]")))
                                   (range) args))
                      [])]
      (into self children))

    ;; map with ≠ 1 key — not a standard JSONLogic op
    :else
    [(problem :warn :op/multi-key (str path)
              (str "rule map has " (count rule) " keys; a JSONLogic op must have exactly 1"))]))

(defn problems
  "Return a vector of validation problems with `rule`."
  [rule]
  (vec (validate-node rule "")))

(defn errors
  "Return only :error-severity problems."
  [rule]
  (filterv #(= :error (:jsonlogic/severity %)) (problems rule)))

(defn valid?
  "True iff `rule` has no :error-level structural problems (warnings are advisory)."
  [rule]
  (empty? (errors rule)))
