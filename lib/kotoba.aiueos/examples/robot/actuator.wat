;; actuator driver — polls cmd (topic 2) and drives it (returns it). Imports only
;; `poll`; it cannot publish.
(module
  (import "aiueos:host" "poll" (func $poll (param i32) (result i64)))
  (memory (export "memory") 1)
  (func (export "tick") (param i64) (result i64)
    (call $poll (i32.const 2))))
