;; A noisy sensor — the README "authoring a component" example, runnable.
;; Imports only the host functions it calls; the manifest grants the matching
;; capabilities. Calling random() without :random/bytes, or publishing to any
;; topic other than 1, would trap.
(module
  (import "aiueos:host" "publish" (func $publish (param i32 i64)))
  (import "aiueos:host" "random"  (func $random  (result i64)))
  (func (export "tick") (result i64)
    (local $r i64)
    (local.set $r (call $random))
    (call $publish (i32.const 1) (local.get $r))
    (local.get $r)))
