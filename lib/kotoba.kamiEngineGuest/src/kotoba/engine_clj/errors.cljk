(ns kotoba.engine-clj.errors
  "Structured compiler errors.

  The cljc analogue of `kami-engine-clj`'s Rust `CljError` enum
  (`{Read, Lower, Codegen, Run}`, `src/lib.rs`). Rust's `Result<_, CljError>`
  short-circuit-return control flow becomes plain Clojure exceptions here:
  each constructor below returns an `ex-info` tagged with
  `:kotoba.engine-clj.errors/kind`, so callers can `ex-data` dispatch on the
  error class exactly like matching on the Rust enum variant.")

(defn read-error
  "Mirrors `CljError::Read` — EDN/reader failure before lowering begins."
  [msg]
  (ex-info (str "read error: " msg) {::kind :read}))

(defn lower-error
  "Mirrors `CljError::Lower` — EDN → AST lowering rejected the input
  (malformed special form, wrong arity, unsupported top-level form, …)."
  [msg]
  (ex-info (str "lowering error: " msg) {::kind :lower}))

(defn codegen-error
  "Mirrors `CljError::Codegen` — AST → instruction-IR codegen failure
  (unbound variable, arity mismatch, `recur` outside a loop, …)."
  [msg]
  (ex-info (str "codegen error: " msg) {::kind :codegen}))

(defn run-error
  "Mirrors `CljError::Run` — reference-interpreter execution failure
  (trap, missing export, …). Stands in for Rust's wasmtime-trap path."
  [msg]
  (ex-info (str "runtime error: " msg) {::kind :run}))

(defn kind
  "The error kind (`:read`/`:lower`/`:codegen`/`:run`) of an exception raised
  by this namespace's constructors, or `nil` for an unrelated exception."
  [ex]
  (::kind (ex-data ex)))
