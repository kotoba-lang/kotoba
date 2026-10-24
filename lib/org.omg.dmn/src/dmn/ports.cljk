(ns dmn.ports
  "Host-injected ports for evaluating a DMN decision table. dmn-clj defines the
  protocols; the host supplies concrete implementations (call a FEEL engine, an
  external rules service, etc.). The evaluator in `dmn.execute` is pure over
  these — no I/O of its own.")

(defprotocol IExpression
  "Evaluate a decision-table input expression against the context map, returning
  the input value to compare against when-cells."
  (eval-input [this expr context] "expr-string + context-map → value"))

(defprotocol IUnary
  "Test whether a when-cell string matches a given input value. Returns boolean."
  (eval-cell [this cell-str input-value] "cell-string + input-value → boolean"))
