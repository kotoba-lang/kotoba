;; T8.3 ADR 0194: pure memory-scan one-shot for HTTP request + result surfaces.
;; No kotoba:typed. Host places bytes in exported memory; guest scans.
;; Symmetric complement to typed packing walks 0192–0193.
;;
;; http_request_scan(url_ptr, url_len, headers_n, body_len, timeout) -> i32
;;   -1 url empty  -2 url>4096  -3 not https://  -4 headers_n  -5 body_len  -6 timeout  0 ok
;;
;; http_response_scan(status, headers_n, body_len) -> i32
;;   -1 status∉[100,599]  -2 headers_n  -3 body_len  0 ok
;;
;; http_error_scan(code_ptr, code_len, msg_len, retryable) -> i32
;;   -1 code empty  -2 code>128  -3 bad code char  -4 msg_len  -5 retryable  0 ok
;;
;; http_result_arm_ok(arm) -> i32
;;   -1 arm∉{0,1}  0 ok

(module $http_memory_scan_v1
  (memory (export "memory") 1)

  ;; code charset [A-Za-z0-9/_:.-] → 1 ok / 0 bad
  (func $code_char_ok (param $c i32) (result i32)
    (local.get $c)
    (i32.const 48)
    (i32.ge_u)
    (local.get $c)
    (i32.const 57)
    (i32.le_u)
    (i32.and)
    (if (result i32)
      (then (i32.const 1))
      (else
        (local.get $c)
        (i32.const 65)
        (i32.ge_u)
        (local.get $c)
        (i32.const 90)
        (i32.le_u)
        (i32.and)
        (if (result i32)
          (then (i32.const 1))
          (else
            (local.get $c)
            (i32.const 97)
            (i32.ge_u)
            (local.get $c)
            (i32.const 122)
            (i32.le_u)
            (i32.and)
            (if (result i32)
              (then (i32.const 1))
              (else
                (local.get $c)
                (i32.const 47)  ;; /
                (i32.eq)
                (local.get $c)
                (i32.const 58)  ;; :
                (i32.eq)
                (i32.or)
                (local.get $c)
                (i32.const 46)  ;; .
                (i32.eq)
                (i32.or)
                (local.get $c)
                (i32.const 45)  ;; -
                (i32.eq)
                (i32.or)
                (local.get $c)
                (i32.const 95)  ;; _
                (i32.eq)
                (i32.or))))))))

  (func (export "http_request_scan")
    (param $url_ptr i32) (param $url_len i32)
    (param $headers_n i32) (param $body_len i32) (param $timeout i32)
    (result i32)
    (if (i32.eqz (local.get $url_len))
      (then (return (i32.const -1))))
    (if (i32.gt_u (local.get $url_len) (i32.const 4096))
      (then (return (i32.const -2))))
    (if (i32.lt_u (local.get $url_len) (i32.const 8))
      (then (return (i32.const -3))))
    ;; https://
    (if (i32.ne (i32.load8_u (local.get $url_ptr)) (i32.const 104))
      (then (return (i32.const -3))))
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
    (if (i32.or (i32.lt_s (local.get $headers_n) (i32.const 0))
                 (i32.gt_s (local.get $headers_n) (i32.const 32)))
      (then (return (i32.const -4))))
    (if (i32.or (i32.lt_s (local.get $body_len) (i32.const 0))
                 (i32.gt_s (local.get $body_len) (i32.const 65536)))
      (then (return (i32.const -5))))
    (if (i32.or (i32.lt_s (local.get $timeout) (i32.const 1))
                 (i32.gt_s (local.get $timeout) (i32.const 30000)))
      (then (return (i32.const -6))))
    (i32.const 0))

  (func (export "http_response_scan")
    (param $status i32) (param $headers_n i32) (param $body_len i32)
    (result i32)
    (if (i32.or (i32.lt_s (local.get $status) (i32.const 100))
                 (i32.gt_s (local.get $status) (i32.const 599)))
      (then (return (i32.const -1))))
    (if (i32.or (i32.lt_s (local.get $headers_n) (i32.const 0))
                 (i32.gt_s (local.get $headers_n) (i32.const 32)))
      (then (return (i32.const -2))))
    (if (i32.or (i32.lt_s (local.get $body_len) (i32.const 0))
                 (i32.gt_s (local.get $body_len) (i32.const 65536)))
      (then (return (i32.const -3))))
    (i32.const 0))

  (func (export "http_error_scan")
    (param $code_ptr i32) (param $code_len i32)
    (param $msg_len i32) (param $retryable i32)
    (result i32)
    (local $i i32) (local $c i32)
    (if (i32.eqz (local.get $code_len))
      (then (return (i32.const -1))))
    (if (i32.gt_u (local.get $code_len) (i32.const 128))
      (then (return (i32.const -2))))
    (local.set $i (i32.const 0))
    (block $done
      (loop $scan
        (br_if $done (i32.ge_u (local.get $i) (local.get $code_len)))
        (local.set $c
          (i32.load8_u (i32.add (local.get $code_ptr) (local.get $i))))
        (if (i32.eqz (call $code_char_ok (local.get $c)))
          (then (return (i32.const -3))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $scan)))
    (if (i32.or (i32.lt_s (local.get $msg_len) (i32.const 0))
                 (i32.gt_s (local.get $msg_len) (i32.const 65536)))
      (then (return (i32.const -4))))
    (if (i32.or (i32.lt_s (local.get $retryable) (i32.const 0))
                 (i32.gt_s (local.get $retryable) (i32.const 1)))
      (then (return (i32.const -5))))
    (i32.const 0))

  (func (export "http_result_arm_ok")
    (param $arm i32) (result i32)
    (if (i32.or (i32.lt_s (local.get $arm) (i32.const 0))
                 (i32.gt_s (local.get $arm) (i32.const 1)))
      (then (return (i32.const -1))))
    (i32.const 0))
)
