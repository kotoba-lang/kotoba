;; errors.cljc — error hierarchy for etzhayyim-sdk (cljc port of errors.py, ADR clj/bb
;; repo rule). The python class tree (EtzhayyimSdkError ⊳ MstProjectorError ⊳ …) becomes
;; a keyword `isa?` graph: every SDK failure is an `ex-info` whose `:type` (in ex-data) is
;; one of the keywords below, `derive`d into the global hierarchy so that
;;   (isa? (:type (ex-data e)) ::error)                 ; "is this any SDK error?"
;;   (isa? (:type (ex-data e)) ::mst-projector-error)   ; "…an mst-projector error?"
;; answer the same questions python answered with `isinstance`. No exception classes are
;; minted — the keyword + ex-info is the cross-platform (clj/cljs/wasm) carrier.
(ns etzhayyim-sdk.errors)

;; ─── Type hierarchy (mirrors the python class tree) ──────────────────
;; base
;;   ::error                         = EtzhayyimSdkError
;; mst_projector
;;   ::mst-projector-error           = MstProjectorError          (→ ::error)
;;   ::mst-projector-network-error   = MstProjectorNetworkError   (→ ::mst-projector-error)
;;   ::mst-projector-server-error    = MstProjectorServerError    (→ ::mst-projector-error)
;;   ::mst-projector-config-error    = raised before any request when no endpoint was
;;                                     configured (→ ::mst-projector-error)
;; mst
;;   ::mst-error                     = MstError                   (→ ::error)
;;   ::mst-network-error             = MstNetworkError            (→ ::mst-error)
;;   ::mst-server-error              = MstServerError             (→ ::mst-error)
;; llm
;;   ::llm-error                     = LlmError                   (→ ::error)
;;   ::llm-network-error             = LlmNetworkError            (→ ::llm-error)
;;   ::llm-auth-error                = LlmAuthError               (→ ::llm-error)
;;   ::llm-rate-limit-error          = LlmRateLimitError          (→ ::llm-error)
;;   ::llm-server-error              = LlmServerError             (→ ::llm-error)
;;   ::llm-config-error              = raised before any request when no endpoint was
;;                                     configured (→ ::llm-error)
;; mst (stub markers — python raised NotImplementedError, not an SDK error)
;;   ::not-implemented               = NotImplementedError analogue (NOT → ::error)

(derive ::mst-projector-error         ::error)
(derive ::mst-projector-network-error ::mst-projector-error)
(derive ::mst-projector-server-error  ::mst-projector-error)
(derive ::mst-projector-config-error  ::mst-projector-error)

(derive ::mst-error         ::error)
(derive ::mst-network-error ::mst-error)
(derive ::mst-server-error  ::mst-error)

(derive ::llm-error            ::error)
(derive ::llm-network-error    ::llm-error)
(derive ::llm-auth-error       ::llm-error)
(derive ::llm-rate-limit-error ::llm-error)
(derive ::llm-server-error     ::llm-error)
(derive ::llm-config-error     ::llm-error)

(defn ex
  "Build an SDK `ex-info` of *type* (one of the keywords above) with message *msg* and
  optional extra ex-data. The hierarchy position rides on `:type`, so a caller can ask
  `(isa? (:type (ex-data e)) ::mst-projector-error)`."
  ([type msg] (ex type msg {}))
  ([type msg data] (ex-info msg (assoc data :type type))))

(defn sdk-error?
  "True when *e* is (or wraps) an etzhayyim-sdk error of *type* (default ::error) — the
  cljc analogue of `isinstance(e, EtzhayyimSdkError)` / a specific subclass."
  ([e] (sdk-error? e ::error))
  ([e type] (boolean (when-let [t (:type (ex-data e))] (isa? t type)))))
