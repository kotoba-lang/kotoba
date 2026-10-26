;; planner (AI agent) — polls scan (topic 1), commands scan*2, publishes to
;; topic 2 ("cmd"). Trusted as :ai-generated: may use the topic bus, but the
;; default policy forbids it network/secrets/persistent-write.
(module
  (import "aiueos:host" "poll"    (func $poll    (param i32) (result i64)))
  (import "aiueos:host" "publish" (func $publish (param i32 i64)))
  (memory (export "memory") 1)
  (func (export "tick") (param i64) (result i64)
    (local $cmd i64)
    (local.set $cmd (i64.mul (call $poll (i32.const 1)) (i64.const 2)))
    (call $publish (i32.const 2) (local.get $cmd))
    (local.get $cmd)))
