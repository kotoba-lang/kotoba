(module
  (import "aiueos.component" "aiueos-clock-now"
    (func $clock-now (param i64) (result i64)))
  (func (export "main") (result i64)
    i64.const 7
    call $clock-now))
