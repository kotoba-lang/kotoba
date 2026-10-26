;; http/fetch — the core, which CANNOT do the work and says so.
;;
;; Every other reference provider in this family is self-contained: sha256
;; hashes, xorshift produces bytes, the clock reads a counter. A network read
;; is different in kind — a wasm core has no socket, and no amount of code here
;; can give it one. The work belongs to the host.
;;
;; So this core exists to FAIL CLOSED. An embedder that links it and forgets to
;; bind a host implementation gets -3 from every call, not silence and not a
;; zero-length body. A capability whose unbound state is indistinguishable from
;; an empty response is a capability that appears to work while reaching
;; nothing — the shape this workspace keeps finding, at the one place where it
;; would mean "the fleet is unreachable and nobody said so".
;;
;; ABI: http_fetch(url-ptr, url-len, out-ptr, out-cap) -> i32
;;   >= 0  bytes written into out-ptr
;;   -1    refused by egress policy      (a decision was made)
;;   -2    transport failed              (a request went out and did not return)
;;   -3    no host provider bound        (nothing was attempted)
;; Three negatives because they are three different facts, and an operator sent
;; to debug the wrong one debugs the wrong thing.
(module
  (memory (export "memory") 1)
  (func (export "http_fetch")
        (param $url_ptr i32) (param $url_len i32)
        (param $out_ptr i32) (param $out_cap i32)
        (result i32)
    (i32.const -3)))
