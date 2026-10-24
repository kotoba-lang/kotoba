(ns systemverilog.assertion
  "SystemVerilog (IEEE 1800) immediate assertion modeling
  (`assert (expr) else $error(msg);`, IEEE 1800 clause 16.4) and a
  tiny evaluator. Out of scope: concurrent assertions and SVA
  temporal properties/sequences.")

(defn make-assertion
  "`expr` is a predicate fn of a state map (the condition being
  asserted); `else-msg` is the message reported on failure."
  [expr else-msg]
  {:expr expr :else-msg else-msg})

(defn check
  "Evaluate an immediate assertion's `:expr` against `state`. Mirrors
  `assert (expr) else $error(msg);`: on success there is no
  `$error` call, so `:message` is `nil`; on failure `:message` is the
  assertion's `:else-msg`."
  [assertion state]
  (let [pass? (boolean ((:expr assertion) state))]
    {:pass? pass?
     :message (when-not pass? (:else-msg assertion))}))

(defn check-all
  "Evaluate a seq of assertions against `state` and return only the
  failures (each as its `check` result) -- a testbench typically only
  cares which immediate assertions tripped."
  [assertions state]
  (->> assertions
       (map #(check % state))
       (remove :pass?)))
