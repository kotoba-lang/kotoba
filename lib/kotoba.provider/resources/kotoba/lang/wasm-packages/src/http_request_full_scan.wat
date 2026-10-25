;; T8.3 ADR 0197: pure memory-scan **full request** one-shot.
;; Composes URL https+bounds (0194) + header set packing table (0196).
;; No kotoba:typed. Component-packable pure path.
;;
;; http_request_full_scan(url_ptr, url_len, headers_n, table_ptr, body_len, timeout) -> i32
;;
;; URL:     -1 empty  -2 >4096  -3 not https://
;; headers: -4 n∉[0,32]
;; pair:    name -11 empty / -12 >128 / -13 non-tchar
;;          value -15 >8192 / -16 NUL|CR|LF
;; body:    -5 len∉[0,65536]
;; timeout: -6 ∉[1,30000]
;; 0 ok
;;
;; Table at table_ptr: n×4 i32 LE [name_ptr, name_len, value_ptr, value_len]

(module $http_request_full_scan_v1
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
    (if (i32.eqz (local.get $len)) (then (return (i32.const -11))))
    (if (i32.gt_u (local.get $len) (i32.const 128)) (then (return (i32.const -12))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $scan
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (local.set $c (i32.load8_u (i32.add (local.get $ptr) (local.get $i))))
        (if (i32.eqz (call $tchar_ok (local.get $c)))
          (then (return (i32.const -13))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (i32.const 0))

  (func $value_scan (param $ptr i32) (param $len i32) (result i32)
    (local $i i32) (local $c i32)
    (if (i32.gt_u (local.get $len) (i32.const 8192)) (then (return (i32.const -15))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $scan
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (local.set $c (i32.load8_u (i32.add (local.get $ptr) (local.get $i))))
        (if (i32.or (i32.eqz (local.get $c))
              (i32.or (i32.eq (local.get $c) (i32.const 10))
                      (i32.eq (local.get $c) (i32.const 13))))
          (then (return (i32.const -16))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (i32.const 0))

  (func $headers_scan (param $n i32) (param $table_ptr i32) (result i32)
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
        (local.set $base
          (i32.add (local.get $table_ptr)
                   (i32.mul (local.get $i) (i32.const 16))))
        (local.set $nptr (i32.load (local.get $base)))
        (local.set $nlen (i32.load (i32.add (local.get $base) (i32.const 4))))
        (local.set $vptr (i32.load (i32.add (local.get $base) (i32.const 8))))
        (local.set $vlen (i32.load (i32.add (local.get $base) (i32.const 12))))
        (local.set $pr (call $name_scan (local.get $nptr) (local.get $nlen)))
        (if (i32.ne (local.get $pr) (i32.const 0))
          (then (return (local.get $pr))))
        (local.set $pr (call $value_scan (local.get $vptr) (local.get $vlen)))
        (if (i32.ne (local.get $pr) (i32.const 0))
          (then (return (local.get $pr))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $walk)))
    (i32.const 0))

  (func (export "http_request_full_scan")
    (param $url_ptr i32) (param $url_len i32)
    (param $headers_n i32) (param $table_ptr i32)
    (param $body_len i32) (param $timeout i32)
    (result i32)
    (local $hr i32)
    ;; url
    (if (i32.eqz (local.get $url_len)) (then (return (i32.const -1))))
    (if (i32.gt_u (local.get $url_len) (i32.const 4096)) (then (return (i32.const -2))))
    (if (i32.lt_u (local.get $url_len) (i32.const 8)) (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (local.get $url_ptr)) (i32.const 104)) (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 1))) (i32.const 116))
      (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 2))) (i32.const 116))
      (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 3))) (i32.const 112))
      (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 4))) (i32.const 115))
      (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 5))) (i32.const 58))
      (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 6))) (i32.const 47))
      (then (return (i32.const -3))))
    (if (i32.ne (i32.load8_u (i32.add (local.get $url_ptr) (i32.const 7))) (i32.const 47))
      (then (return (i32.const -3))))
    ;; headers table
    (local.set $hr (call $headers_scan (local.get $headers_n) (local.get $table_ptr)))
    (if (i32.ne (local.get $hr) (i32.const 0))
      (then (return (local.get $hr))))
    ;; body + timeout
    (if (i32.or (i32.lt_s (local.get $body_len) (i32.const 0))
                 (i32.gt_s (local.get $body_len) (i32.const 65536)))
      (then (return (i32.const -5))))
    (if (i32.or (i32.lt_s (local.get $timeout) (i32.const 1))
                 (i32.gt_s (local.get $timeout) (i32.const 30000)))
      (then (return (i32.const -6))))
    (i32.const 0))
)
