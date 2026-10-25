;; T8.3 ADR 0195: pure memory-scan one-shot for HTTP header name/value/pair.
;; Complements typed 0187–0188 and pure request/result scan 0194.
;; No kotoba:typed. Host places bytes in exported memory.
;;
;; http_header_name_scan(ptr,len) -> i32
;;   -1 empty  -2 >128  -3 non-tchar  0 ok
;; tchar: ALPHA / DIGIT / !#$%&'*+-.^_`|~
;;
;; http_header_value_scan(ptr,len) -> i32
;;   -2 >8192  -3 NUL/CR/LF  0 ok (empty allowed)
;;
;; http_header_pair_scan(nptr,nlen,vptr,vlen) -> i32
;;   name codes -1/-2/-3; value -2→-5, -3→-6; 0 ok

(module $http_header_memory_scan_v1
  (memory (export "memory") 1)

  (func $tchar_ok (param $c i32) (result i32)
    ;; digit
    (local.get $c) (i32.const 48) (i32.ge_u)
    (local.get $c) (i32.const 57) (i32.le_u)
    (i32.and)
    (if (result i32) (then (i32.const 1))
      (else
        ;; A-Z
        (local.get $c) (i32.const 65) (i32.ge_u)
        (local.get $c) (i32.const 90) (i32.le_u)
        (i32.and)
        (if (result i32) (then (i32.const 1))
          (else
            ;; a-z
            (local.get $c) (i32.const 97) (i32.ge_u)
            (local.get $c) (i32.const 122) (i32.le_u)
            (i32.and)
            (if (result i32) (then (i32.const 1))
              (else
                ;; ! # $ % & ' * + - . ^ _ ` | ~
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
        ;; NUL CR LF
        (if (i32.or (i32.eqz (local.get $c))
              (i32.or (i32.eq (local.get $c) (i32.const 10))
                      (i32.eq (local.get $c) (i32.const 13))))
          (then (return (i32.const -3))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (i32.const 0))

  (func (export "http_header_name_scan")
    (param $ptr i32) (param $len i32) (result i32)
    (call $name_scan (local.get $ptr) (local.get $len)))

  (func (export "http_header_value_scan")
    (param $ptr i32) (param $len i32) (result i32)
    (call $value_scan (local.get $ptr) (local.get $len)))

  (func (export "http_header_pair_scan")
    (param $nptr i32) (param $nlen i32)
    (param $vptr i32) (param $vlen i32)
    (result i32)
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
)
