(module
  (import "kotoba" "http_post"
    (func $http_post (param i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  ;; url at 0: "http://example.test/echo" (24 bytes) — length 24
  (data (i32.const 0) "http://example.test/echo")
  ;; body at 32: "ping" (4 bytes)
  (data (i32.const 32) "ping")
  (func (export "main") (result i64)
    ;; out at 64, cap 256
    (i64.extend_i32_s
      (call $http_post
        (i32.const 0) (i32.const 24)
        (i32.const 32) (i32.const 4)
        (i32.const 64) (i32.const 256)))))
