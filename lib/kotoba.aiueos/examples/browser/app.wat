(module
  (import "aiueos:host" "dom-render" (func $render (param i32 i32)))
  (import "aiueos:host" "dom-event" (func $event (param i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "<main><h1>aiueos browser surface</h1><p>rendered by /init-capable aiueos</p></main>")
  (func (export "run") (result i64)
    (call $render (i32.const 0) (i32.const 83))
    (drop (call $event (i32.const 128) (i32.const 64)))
    (i64.const 83)))
