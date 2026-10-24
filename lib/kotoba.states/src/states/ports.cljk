(ns states.ports
  "Host-injected ports for executing an ASL state machine. states-clj defines the
  protocol; the host supplies a concrete implementation (call a Lambda, an external
  service, a test stub, …). The interpreter in `states.execute` is pure
  orchestration over these — no I/O of its own.")

(defprotocol ITask
  "Side-effecting interface for a :task state. `run` receives the state map and
  the current input data, and returns the (possibly updated) output data."
  (run [this state input-data] "state-map + input-data → output-data"))
