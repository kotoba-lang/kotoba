(module
  (global $t (mut i64) (i64.const 0))
  (func (export "clock_monotonic") (result i64)
    (global.set $t (i64.add (global.get $t) (i64.const 1)))
    (global.get $t)))
