;; llm/infer — the core, which CANNOT do the work and says so.
;;
;; Same shape and the same reason as `capability-http-fetch`'s core: a wasm
;; core has no socket, and no amount of code here can give it one. It exists to
;; FAIL CLOSED, so an embedder that links it and forgets to bind a host
;; implementation gets -3 from every call rather than silence, a zero-length
;; body, or an empty completion.
;;
;; An empty completion is the specific hazard here. `http/fetch` unbound could
;; look like an empty HTTP response; `llm/infer` unbound would look like a
;; model that had nothing to say — which is a thing models actually do. A
;; capability whose unbound state is indistinguishable from a real answer is a
;; capability that appears to work while reaching nothing.
;;
;; ABI: llm_infer(model-ptr, model-len, prompt-ptr, prompt-len,
;;                out-ptr, out-cap) -> i32
;;   >= 0  bytes written into out-ptr
;;   -1    refused by policy           (a decision was made)
;;   -2    transport failed            (a request went out and did not return)
;;   -3    no host provider bound      (nothing was attempted)
;;
;; Three negatives because they are three different facts, and an operator sent
;; to debug the wrong one debugs the wrong thing (ADR-2608136000).
;;
;; The model is a parameter and the ENDPOINT is not. The guest names which
;; model it wants; where that model is served is the host's to decide, and a
;; guest that could pass an endpoint could send its prompt anywhere.
(module
  (memory (export "memory") 1)
  (func (export "llm_infer")
        (param $model_ptr i32) (param $model_len i32)
        (param $prompt_ptr i32) (param $prompt_len i32)
        (param $out_ptr i32) (param $out_cap i32)
        (result i32)
    (i32.const -3)))
