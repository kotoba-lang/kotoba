;; T8.3 ADR 0198: pure memory-scan **full result** one-shot.
;; Composes response surface + header set table (ok arm) or error code scan.
;; Symmetric to full request scan 0197. No kotoba:typed. Component-packable.
;;
;; http_result_full_scan(arm, status, headers_n, table_ptr, body_len,
;;                       code_ptr, code_len, msg_len, retryable) -> i32
;;
;; arm: -1 ∉{0,1}  (0=:ok 1=:error)
;; ok arm:
;;   -2 status∉[100,599]
;;   -4 headers_n∉[0,32]
;;   -11/-12/-13 name empty/>128/non-tchar
;;   -15/-16 value >8192 / NUL|CR|LF
;;   -3 body_len∉[0,65536]
;; error arm:
;;   -21 code empty  -22 code>128  -23 bad char
;;   -24 msg_len∉[0,65536]  -25 retryable∉{0,1}
;; 0 ok
;;
;; Header table layout matches ADR 0196 (n×4 i32 LE).

(module $http_result_full_scan_v1
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

  (func $code_char_ok (param $c i32) (result i32)
    ;; [A-Za-z0-9/_:.-]
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
                (local.get $c) (i32.const 47) (i32.eq)
                (local.get $c) (i32.const 58) (i32.eq) (i32.or)
                (local.get $c) (i32.const 46) (i32.eq) (i32.or)
                (local.get $c) (i32.const 45) (i32.eq) (i32.or)
                (local.get $c) (i32.const 95) (i32.eq) (i32.or))))))))

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

  (func $error_scan (param $code_ptr i32) (param $code_len i32)
                    (param $msg_len i32) (param $retryable i32) (result i32)
    (local $i i32) (local $c i32)
    (if (i32.eqz (local.get $code_len)) (then (return (i32.const -21))))
    (if (i32.gt_u (local.get $code_len) (i32.const 128)) (then (return (i32.const -22))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $scan
        (br_if $done (i32.ge_u (local.get $i) (local.get $code_len)))
        (local.set $c (i32.load8_u (i32.add (local.get $code_ptr) (local.get $i))))
        (if (i32.eqz (call $code_char_ok (local.get $c)))
          (then (return (i32.const -23))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (if (i32.or (i32.lt_s (local.get $msg_len) (i32.const 0))
                 (i32.gt_s (local.get $msg_len) (i32.const 65536)))
      (then (return (i32.const -24))))
    (if (i32.or (i32.lt_s (local.get $retryable) (i32.const 0))
                 (i32.gt_s (local.get $retryable) (i32.const 1)))
      (then (return (i32.const -25))))
    (i32.const 0))

  (func (export "http_result_full_scan")
    (param $arm i32)
    (param $status i32) (param $headers_n i32) (param $table_ptr i32)
    (param $body_len i32)
    (param $code_ptr i32) (param $code_len i32)
    (param $msg_len i32) (param $retryable i32)
    (result i32)
    (local $hr i32)
    (if (i32.or (i32.lt_s (local.get $arm) (i32.const 0))
                 (i32.gt_s (local.get $arm) (i32.const 1)))
      (then (return (i32.const -1))))
    (if (i32.eq (local.get $arm) (i32.const 0))
      (then
        ;; ok arm
        (if (i32.or (i32.lt_s (local.get $status) (i32.const 100))
                     (i32.gt_s (local.get $status) (i32.const 599)))
          (then (return (i32.const -2))))
        (local.set $hr (call $headers_scan (local.get $headers_n) (local.get $table_ptr)))
        (if (i32.ne (local.get $hr) (i32.const 0))
          (then (return (local.get $hr))))
        (if (i32.or (i32.lt_s (local.get $body_len) (i32.const 0))
                     (i32.gt_s (local.get $body_len) (i32.const 65536)))
          (then (return (i32.const -3))))
        (return (i32.const 0))))
    ;; error arm
    (call $error_scan (local.get $code_ptr) (local.get $code_len)
                      (local.get $msg_len) (local.get $retryable)))
)
