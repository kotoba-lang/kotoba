(ns jsonlogic.ports
  "Host-injected ports for JSONLogic evaluation. jsonlogic-clj defines the
  protocol; the host supplies custom operator implementations. The evaluator
  in `jsonlogic.core` is pure over these — no I/O of its own.")

(defprotocol IOp
  "Custom operator extension point. Implement to add operators beyond the
  built-in JSONLogic set. `apply-op` receives pre-evaluated args."
  (custom-op? [this name]           "Returns true if this host handles operator `name`.")
  (apply-op   [this name args data] "Apply custom operator `name` to pre-evaluated `args` against `data`."))

(def default-ports
  "A no-op IOp that handles no custom operators (only built-ins are used)."
  (reify IOp
    (custom-op? [_ _] false)
    (apply-op   [_ op _ _]
      (throw (ex-info (str "Unknown JSONLogic operator: " op)
                      {:jsonlogic/op op})))))
