(module
  ;; The Arrow IPC file is placed directly in this owned ingress memory.  The
  ;; kernel receives the borrowed values-buffer byte offset, not a copied array.
  (memory (export "memory") 1)

  (func (export "scale_f32x4")
        (param $ptr i32) (param $length i32) (param $scale f32)
    (local $i i32)
    (local $vector-length i32)
    (local $address i32)

    (local.set $vector-length
      (i32.and (local.get $length) (i32.const -4)))

    (block $vector-done
      (loop $vector-loop
        (br_if $vector-done
          (i32.ge_u (local.get $i) (local.get $vector-length)))
        (local.set $address
          (i32.add (local.get $ptr)
                   (i32.shl (local.get $i) (i32.const 2))))
        (v128.store (local.get $address)
          (f32x4.mul
            (v128.load (local.get $address))
            (f32x4.splat (local.get $scale))))
        (local.set $i (i32.add (local.get $i) (i32.const 4)))
        (br $vector-loop)))

    ;; Preserve exact semantics for columns whose row count is not a multiple
    ;; of four instead of reading across the Arrow buffer boundary.
    (block $tail-done
      (loop $tail-loop
        (br_if $tail-done
          (i32.ge_u (local.get $i) (local.get $length)))
        (local.set $address
          (i32.add (local.get $ptr)
                   (i32.shl (local.get $i) (i32.const 2))))
        (f32.store (local.get $address)
          (f32.mul (f32.load (local.get $address)) (local.get $scale)))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $tail-loop))))

  ;; Same memory and operation as the vector kernel, deliberately expressed
  ;; with scalar Wasm instructions to provide a like-for-like benchmark oracle.
  (func (export "scale_f32_scalar")
        (param $ptr i32) (param $length i32) (param $scale f32)
    (local $i i32)
    (local $address i32)
    (block $done
      (loop $loop
        (br_if $done (i32.ge_u (local.get $i) (local.get $length)))
        (local.set $address
          (i32.add (local.get $ptr)
                   (i32.shl (local.get $i) (i32.const 2))))
        (f32.store (local.get $address)
          (f32.mul (f32.load (local.get $address)) (local.get $scale)))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $loop))))
)
