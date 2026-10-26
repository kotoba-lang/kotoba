(module
  (import "kotoba" "http_post"
    (func $http_post (param i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "https://api.example.test/v1/messages")
  (data (i32.const 64) "hello")
  (func (export "main") (result i32)
    (call $http_post
      (i32.const 0) (i32.const 36)
      (i32.const 64) (i32.const 5)
      (i32.const 128) (i32.const 128))))
