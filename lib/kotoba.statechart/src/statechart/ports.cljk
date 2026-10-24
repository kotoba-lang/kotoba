(ns statechart.ports
  "Host-injected ports for executing a statechart. statechart-clj defines the
  protocols; the host supplies concrete implementations (call a service, evaluate
  an expression, enqueue an actor message, …). The interpreter in
  `statechart.execute` is pure orchestration over these — no I/O of its own.")

(defprotocol IAction
  "Side-effect of entering/exiting a state or firing a transition.
  `run` receives the action name string and current context map, returns ctx'."
  (run [this action-name ctx] "action-name → ctx → ctx'"))

(defprotocol IGuard
  "Guard condition on a transition. `allow?` receives the condition name string
  (may be nil, meaning unconditional) and the current context, returns boolean."
  (allow? [this cond-name ctx] "cond-name → ctx → boolean"))
