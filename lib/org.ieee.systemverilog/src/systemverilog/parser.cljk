(ns systemverilog.parser
  "A simplified, line-based recognizer for a small subset of
  SystemVerilog (IEEE 1800) source text, producing the data models
  from `systemverilog.datatype`/`interface`/`class`/`assertion`.

  This is not a real parser: no preprocessor, no nesting, and at most
  one construct per line. It recognizes exactly: `interface NAME;` /
  `endinterface`, `class NAME [extends PARENT];` / `endclass`,
  `logic [N:0] name;` / `bit name;` declarations, and
  `assert (expr) else $error(msg);` statements."
  (:require [kotoba.lang.text :as str]
            [systemverilog.datatype :as datatype]
            [systemverilog.interface :as iface]
            [systemverilog.class :as sv-class]
            [systemverilog.assertion :as assertion]))

(def ^:private interface-open-re #"^\s*interface\s+(\w+)\s*;\s*$")
(def ^:private interface-close-re #"^\s*endinterface\s*;?\s*$")
(def ^:private class-open-extends-re #"^\s*class\s+(\w+)\s+extends\s+(\w+)\s*;\s*$")
(def ^:private class-open-plain-re #"^\s*class\s+(\w+)\s*;\s*$")
(def ^:private class-close-re #"^\s*endclass\s*;?\s*$")
(def ^:private logic-decl-re #"^\s*logic\s*\[(\d+):0\]\s*(\w+)\s*;\s*$")
(def ^:private bit-decl-re #"^\s*bit\s+(\w+)\s*;\s*$")
(def ^:private assert-re #"^\s*assert\s*\((.*)\)\s*else\s*\$error\((.*)\)\s*;\s*$")
(def ^:private cmp-re #"^\s*(\w+)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)\s*$")

(defn- parse-int
  [s]
  #?(:clj (Long/parseLong s)
     :cljs (js/parseInt s 10)))

(defn- strip-quotes
  [s]
  (let [s (str/trim s)]
    (if (and (> (count s) 1) (str/starts-with? s "\"") (str/ends-with? s "\""))
      (subs s 1 (dec (count s)))
      s)))

(defn- compile-expr
  "Compile the tiny `var OP int-literal` subset of expressions into a
  predicate fn of a state map, e.g. `(compile-expr \"count > 0\")`
  matches `(fn [state] (> (:count state) 0))`. Anything more
  complex (this is a simplified subset, not a full expression
  evaluator) compiles to an always-failing predicate that still
  retains the original source text as metadata for inspection."
  [expr-src]
  (if-let [[_ var-name op lit] (re-matches cmp-re (str/trim expr-src))]
    (let [k (keyword var-name)
          n (parse-int lit)
          op-fn (case op "==" = "!=" not= ">" > "<" < ">=" >= "<=" <=)]
      (with-meta (fn [state] (op-fn (get state k) n)) {:source expr-src}))
    (with-meta (constantly false) {:source expr-src})))

(defn- blank-result [] {:interfaces [] :classes [] :assertions [] :signals []})

(defn- add-decl
  "Route a parsed signal declaration to the interface/class currently
  open (`current`), or into the top-level `:signals` bucket of
  `result` when no block is open. Returns `[current' result']`."
  [mode current result sig]
  (case mode
    :interface [(update current :signals conj sig) result]
    :class [(update current :fields conj sig) result]
    [current (update result :signals conj sig)]))

(defn parse
  "Parse `text` (a SystemVerilog source string) into
  `{:interfaces [...] :classes [...] :assertions [...] :signals [...]}`
  using the models from `systemverilog.interface`/`class`/`assertion`/
  `datatype`. `:signals` collects any `logic`/`bit` declarations found
  outside of an interface or class body."
  [text]
  (loop [lines (str/split-lines text)
         mode :top
         current nil
         result (blank-result)]
    (if (empty? lines)
      result
      (let [line (first lines)
            more (rest lines)]
        (cond
          (re-matches interface-open-re line)
          (recur more :interface
                 (iface/make-interface (keyword (second (re-matches interface-open-re line))) [] {})
                 result)

          (re-matches interface-close-re line)
          (recur more :top nil (update result :interfaces conj current))

          (re-matches class-open-extends-re line)
          (let [[_ name extends] (re-matches class-open-extends-re line)]
            (recur more :class (sv-class/make-class (keyword name) (keyword extends) [] []) result))

          (re-matches class-open-plain-re line)
          (let [[_ name] (re-matches class-open-plain-re line)]
            (recur more :class (sv-class/make-class (keyword name) nil [] []) result))

          (re-matches class-close-re line)
          (recur more :top nil (update result :classes conj current))

          (re-matches logic-decl-re line)
          (let [[_ msb name] (re-matches logic-decl-re line)
                sig (datatype/signal (keyword name) :logic (inc (parse-int msb)))
                [current' result'] (add-decl mode current result sig)]
            (recur more mode current' result'))

          (re-matches bit-decl-re line)
          (let [[_ name] (re-matches bit-decl-re line)
                sig (datatype/signal (keyword name) :bit 1)
                [current' result'] (add-decl mode current result sig)]
            (recur more mode current' result'))

          (re-matches assert-re line)
          (let [[_ expr-src msg-src] (re-matches assert-re line)]
            (recur more mode current
                   (update result :assertions conj
                           (assertion/make-assertion (compile-expr expr-src) (strip-quotes msg-src)))))

          :else
          (recur more mode current result))))))
