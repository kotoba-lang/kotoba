(module
  (import "aiueos:host" "input-event" (func $event (param i32 i32) (result i32)))
  (memory (export "memory") 1)
  (func (export "run") (result i64)
    (i64.extend_i32_s (call $event (i32.const 64) (i32.const 64)))))
