(module
  (import "aiueos:host" "fb-present"
    (func $present (param i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  ;; Two RGBA pixels: red, green.
  (data (i32.const 0) "\ff\00\00\ff\00\ff\00\ff")
  (func (export "run") (result i64)
    (i64.extend_i32_s
      (call $present
        (i32.const 0)  ;; ptr
        (i32.const 8)  ;; len
        (i32.const 2)  ;; width
        (i32.const 1)  ;; height
        (i32.const 8)))))
