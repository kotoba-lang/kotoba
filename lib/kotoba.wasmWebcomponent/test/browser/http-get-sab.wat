(module
  (import "kotoba" "http_get"
    (func $http_get (param i32 i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "example.test")
  (data (i32.const 32) "/bounded")
  (func (export "main") (result i32)
    (call $http_get
      (i32.const 0) (i32.const 12) (i32.const 443)
      (i32.const 32) (i32.const 8)
      (i32.const 64) (i32.const 128))))
