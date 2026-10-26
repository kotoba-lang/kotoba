;; Kotoba ABI guest for :app/notes (hosted P3). Same bytes as the
;; base64 fixture in aiueos.session.guest / aiueos.execute-test.
;; (import "kotoba" "log_write") — grant must admit :log/write or this
;; never links. Not a JS app; not POSIX :fs/open.
(module
  (import "kotoba" "log_write" (func $log_write (param i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "hi")
  (func (export "main") (result i32)
    i32.const 0
    i32.const 2
    call $log_write))
