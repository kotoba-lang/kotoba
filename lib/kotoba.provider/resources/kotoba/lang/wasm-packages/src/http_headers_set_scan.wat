;; T8.3 ADR 0196: pure memory-scan one-shot for HTTP header **set packing**.
;; Complements typed walk 0189 and single-pair scan 0195. No kotoba:typed.
;;
;; Layout at table_ptr: n records of 4×i32 little-endian:
;;   [name_ptr, name_len, value_ptr, value_len] × n
;; name_ptr/value_ptr are absolute offsets into the same linear memory.
;;
;; http_headers_set_scan(n, table_ptr) -> i32
;;   -4 n∉[0,32]
;;   per pair: name -1 empty / -2 >128 / -3 non-tchar
;;             value -2→-5 >8192 / -3→-6 NUL|CR|LF
;;   0 ok (n=0 allowed; uniqueness not checked)

(module $http_headers_set_scan_v1
  (memory (export "memory") 1)

  (func $tchar_ok (param $c i32) (result i32)
    (local.get $c) (i32.const 48) (i32.ge_u)
    (local.get $c) (i32.const 57) (i32.le_u)
    (i32.and)
    (if (result i32) (then (i32.const 1))
      (else
        (local.get $c) (i32.const 65) (i32.ge_u)
        (local.get $c) (i32.const 90) (i32.le_u)
        (i32.and)
        (if (result i32) (then (i32.const 1))
          (else
            (local.get $c) (i32.const 97) (i32.ge_u)
            (local.get $c) (i32.const 122) (i32.le_u)
            (i32.and)
            (if (result i32) (then (i32.const 1))
              (else
                (local.get $c) (i32.const 33) (i32.eq)
                (local.get $c) (i32.const 35) (i32.eq) (i32.or)
                (local.get $c) (i32.const 36) (i32.eq) (i32.or)
                (local.get $c) (i32.const 37) (i32.eq) (i32.or)
                (local.get $c) (i32.const 38) (i32.eq) (i32.or)
                (local.get $c) (i32.const 39) (i32.eq) (i32.or)
                (local.get $c) (i32.const 42) (i32.eq) (i32.or)
                (local.get $c) (i32.const 43) (i32.eq) (i32.or)
                (local.get $c) (i32.const 45) (i32.eq) (i32.or)
                (local.get $c) (i32.const 46) (i32.eq) (i32.or)
                (local.get $c) (i32.const 94) (i32.eq) (i32.or)
                (local.get $c) (i32.const 95) (i32.eq) (i32.or)
                (local.get $c) (i32.const 96) (i32.eq) (i32.or)
                (local.get $c) (i32.const 124) (i32.eq) (i32.or)
                (local.get $c) (i32.const 126) (i32.eq) (i32.or))))))))

  (func $name_scan (param $ptr i32) (param $len i32) (result i32)
    (local $i i32) (local $c i32)
    (if (i32.eqz (local.get $len)) (then (return (i32.const -1))))
    (if (i32.gt_u (local.get $len) (i32.const 128)) (then (return (i32.const -2))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $scan
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (local.set $c (i32.load8_u (i32.add (local.get $ptr) (local.get $i))))
        (if (i32.eqz (call $tchar_ok (local.get $c)))
          (then (return (i32.const -3))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (i32.const 0))

  (func $value_scan (param $ptr i32) (param $len i32) (result i32)
    (local $i i32) (local $c i32)
    (if (i32.gt_u (local.get $len) (i32.const 8192)) (then (return (i32.const -2))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $scan
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (local.set $c (i32.load8_u (i32.add (local.get $ptr) (local.get $i))))
        (if (i32.or (i32.eqz (local.get $c))
              (i32.or (i32.eq (local.get $c) (i32.const 10))
                      (i32.eq (local.get $c) (i32.const 13))))
          (then (return (i32.const -3))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (i32.const 0))

  (func $pair_scan (param $nptr i32) (param $nlen i32)
                   (param $vptr i32) (param $vlen i32) (result i32)
    (local $nr i32) (local $vr i32)
    (local.set $nr (call $name_scan (local.get $nptr) (local.get $nlen)))
    (if (i32.ne (local.get $nr) (i32.const 0))
      (then (return (local.get $nr))))
    (local.set $vr (call $value_scan (local.get $vptr) (local.get $vlen)))
    (if (i32.eq (local.get $vr) (i32.const -2))
      (then (return (i32.const -5))))
    (if (i32.eq (local.get $vr) (i32.const -3))
      (then (return (i32.const -6))))
    (local.get $vr))

  ;; load i32 LE from memory
  (func $load_i32 (param $p i32) (result i32)
    (i32.load (local.get $p)))

  (func (export "http_headers_set_scan")
    (param $n i32) (param $table_ptr i32) (result i32)
    (local $i i32) (local $base i32)
    (local $nptr i32) (local $nlen i32) (local $vptr i32) (local $vlen i32)
    (local $pr i32)
    (if (i32.or (i32.lt_s (local.get $n) (i32.const 0))
                 (i32.gt_s (local.get $n) (i32.const 32)))
      (then (return (i32.const -4))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $walk
        (br_if $done (i32.ge_s (local.get $i) (local.get $n)))
        ;; base = table_ptr + i*16
        (local.set $base
          (i32.add (local.get $table_ptr)
                   (i32.mul (local.get $i) (i32.const 16))))
        (local.set $nptr (call $load_i32 (local.get $base)))
        (local.set $nlen (call $load_i32 (i32.add (local.get $base) (i32.const 4))))
        (local.set $vptr (call $load_i32 (i32.add (local.get $base) (i32.const 8))))
        (local.set $vlen (call $load_i32 (i32.add (local.get $base) (i32.const 12))))
        (local.set $pr
          (call $pair_scan (local.get $nptr) (local.get $nlen)
                           (local.get $vptr) (local.get $vlen)))
        (if (i32.ne (local.get $pr) (i32.const 0))
          (then (return (local.get $pr))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $walk)))
    (i32.const 0))
)
