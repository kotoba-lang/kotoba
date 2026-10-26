;; sensor driver — reads the hardware (arg) and publishes it to topic 1 ("scan").
;; Imports only `publish`; calling `poll` would trap (capability not granted).
(module
  (import "aiueos:host" "publish" (func $publish (param i32 i64)))
  (memory (export "memory") 1)
  (func (export "tick") (param $reading i64) (result i64)
    (call $publish (i32.const 1) (local.get $reading))
    (local.get $reading)))
