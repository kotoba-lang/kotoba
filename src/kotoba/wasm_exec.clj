(ns kotoba.wasm-exec
  "Actually EXECUTE the bytes `kotoba.runtime/wasm-binary` emits, via
  com.dylibso.chicory (a pure-JVM WebAssembly runtime — no native toolchain,
  no wasmtime/wasmer process). This is the piece that closes the
  compile -> check -> emit -> RUN loop: until this namespace existed, nothing
  in this repository ever ran the emitted module, only inspected its byte
  layout (magic bytes, import/function counts).

  Host functions here are a thin (Instance memory ptr/len) <-> EDN adapter
  over the pure `kotoba.kgraph` store, matching the (ptr,len[,out-ptr,out-cap])
  ABI already used by the existing string-passing host imports
  (clipboard-write-str, http-fetch, ...). A production host (browser,
  Cloudflare Worker, ...) implements the SAME (module=\"kotoba\", field) import
  surface in its own runtime; this namespace is the JVM one, used here to
  prove — not just assert — that emitted modules run.

  Runtime capability enforcement (ADR-2607050500): `kotoba.runtime/check`
  only refuses to EMIT a host import a compile-time policy doesn't allow —
  it says nothing about what actually happens when the resulting bytes are
  RUN, and until now `has-capability-fn` was a permissive stub that granted
  every capability id unconditionally regardless of any policy. `instantiate`
  / `run-main` now take an optional POLICY (same EDN vocabulary as
  kotoba.host-providers/kotoba.runtime/check) and build a real
  `has_capability` host function that maps the i32 id the guest passes back
  to a capability name (via kotoba.runtime/capability-contract) and checks it
  against POLICY — no POLICY means nothing is granted (fail closed), not the
  previous always-1 behavior. `kgraph-host-functions`' 2-/3-arg forms extend
  the same fail-closed guarding (via kotoba.lang.capability-host/guard-call,
  mirroring kotoba.host-providers/host-call) to the effectful kgraph-* ops
  themselves, not just the has-capability? query; the 1-arg form stays
  unguarded for backward compatibility (see its docstring). A per-instance
  instruction-count fuel limit (`fuel-listener`, wired into `instantiate` via
  com.dylibso.chicory.runtime.Instance.Builder/withUnsafeExecutionListener)
  bounds execution against a runaway/looping guest instead of hanging or
  blowing the JVM stack uncontrolled."
  (:require [clojure.edn :as edn]
            [kotoba.host-providers :as host-providers]
            [kotoba.kgraph :as kgraph]
            [kotoba.lang.capability-host :as capability-host]
            [kotoba.lang.capability-values :as capability-values]
            [kotoba.runtime :as runtime])
  (:import (com.dylibso.chicory.runtime ExecutionListener HostFunction ImportFunction
                                        ImportValues Instance WasmFunctionHandle)
           (com.dylibso.chicory.wasm Parser)
           (com.dylibso.chicory.wasm.types FunctionType ValType)))

(defn- read-str
  "UTF-8 string at [ptr, ptr+len) in INSTANCE's exported linear memory."
  [instance ptr len]
  (.readString (.memory instance) (int ptr) (int len)))

(defn- write-bytes!
  "Write BS into INSTANCE's memory at PTR (capacity CAP bytes); returns the
  byte count written, or -1 when BS would overflow CAP (the caller's buffer
  was too small — mirrors the existing result-err?/negative-status ABI)."
  [instance ptr cap bs]
  (let [n (count bs)]
    (if (> n cap)
      -1
      (do (.write (.memory instance) (int ptr) (byte-array bs) 0 n)
          n))))

(defn host-fn
  "One (module \"kotoba\") host import: FIELD, param/result ValTypes, and a
  Clojure fn [instance long-args] -> long (the single i32/i64 result;
  this repo's host-import contract never returns more than one value)."
  [field params result f]
  (HostFunction. "kotoba" field
                 (FunctionType/of params [result])
                 (reify WasmFunctionHandle
                   (apply [_ instance args]
                     (long-array [(f instance args)])))))

(def ^:private valtype {:i32 ValType/I32 :i64 ValType/I64})

(defn stub-host-function
  "A trivial always-0 HostFunction for one host-import descriptor
  ({:field :params :result}, values from kotoba.runtime/host-imports — module
  is always \"kotoba\" in this contract). For host imports a caller doesn't
  need real behavior for; mirrors kotoba.host-providers/default-handlers'
  stub convention on the WASM side, so `kotoba wasm run` never fails to link
  a valid program just because it also happens to call e.g. notify-show."
  [{:keys [field params result]}]
  (host-fn field (mapv valtype params) (valtype result) (fn [_instance _args] 0)))

(def ^:private id->capability-name
  "Reverse of kotoba.runtime/capability-contract's :capability-ids
  (capability-name string -> i32 id): the compiled guest only ever pushes
  the STATIC id resolved at compile time from a literal capability keyword
  (kotoba.runtime/compile-wasm-expr's `has-capability?` case, via
  kotoba.runtime/capability-id); this is how the RUN-time `has_capability`
  host import maps that id back to a name comparable against a policy."
  (into {} (map (fn [[cap-name id]] [id cap-name]))
        (:capability-ids runtime/capability-contract)))

(defn capability-granted?
  "Whether capability id ID (as received by the `has_capability` host
  import, see `id->capability-name`) is granted under POLICY — the same EDN
  vocabulary as kotoba.host-providers/kotoba.runtime/check
  (:kotoba.policy/capabilities #{...}). A nil/unrecognized POLICY or id
  grants nothing: fail closed, not fail open."
  [policy id]
  (boolean (when-let [cap-name (get id->capability-name id)]
             (contains? (runtime/policy-capabilities policy) cap-name))))

(defn has-capability-fn
  "Real `has_capability` host import: maps the i32 capability id the
  compiled guest passes back to a capability name and checks it against
  POLICY (see `capability-granted?`). No POLICY (the 0-arg form, and the
  default when `instantiate`/`run-main` are called without one) grants
  NOTHING — every capability id resolves to 0 (denied). This replaces the
  previous stub that always answered 1 (granted) regardless of id or policy,
  which meant `has-capability?` was runtime-meaningless: the static
  compile-time gate (kotoba.runtime/check) was the only enforcement, and it
  only holds if the bytes actually running here were compiled under, and
  never separated from, the intended policy — nothing at this boundary
  verified that."
  ([] (has-capability-fn nil))
  ([policy]
   (host-fn "has_capability" [ValType/I32] ValType/I32
            (fn [_instance args]
              (if (capability-granted? policy (aget args 0)) 1 0)))))

(def default-fuel-limit
  "Default max WASM-instruction budget for one `instantiate`d Instance's
  execution (see `fuel-listener`) when POLICY doesn't carry an explicit
  :kotoba.policy/fuel. Every demo program in this repo runs a few dozen
  instructions at most, so this is orders of magnitude beyond legitimate
  use, while still tripping a genuinely unbounded loop/recursion in a small
  fraction of a second instead of hanging the process or exhausting the JVM
  call stack uncontrolled."
  5000000)

(defn- fuel-limit [policy]
  (or (:kotoba.policy/fuel policy) default-fuel-limit))

(defn fuel-listener
  "com.dylibso.chicory.runtime.ExecutionListener enforcing a hard cap of
  LIMIT WASM instructions dispatched during one Instance's execution.
  Verified against com.dylibso.chicory:runtime:1.4.0's own bytecode
  (Instance/onExecution, called from InterpreterMachine's per-instruction
  dispatch loop, invokes ExecutionListener/onExecution exactly once per
  instruction actually executed — including every iteration of a loop and
  every recursive call, not merely once per top-level `call`): this is a
  real per-instruction hook Chicory exposes, not a wall-clock timeout or an
  approximation. Throws ex-info {:kotoba.wasm/problem :fuel-exhausted
  :kotoba.wasm/fuel-limit LIMIT} once the budget is exceeded, aborting the
  in-flight WASM call instead of letting it run — or recurse — unbounded."
  [limit]
  (let [n (atom 0)]
    (reify ExecutionListener
      (onExecution [_ _instruction _stack]
        (when (> (swap! n inc) limit)
          (throw (ex-info "wasm execution exceeded fuel limit"
                          {:kotoba.wasm/problem :fuel-exhausted
                           :kotoba.wasm/fuel-limit limit})))))))

(defn- kgraph-effects
  "Raw (uninstrumented) (fn [instance args] -> long) bodies for the four
  kgraph-* ops against STORE — factored out so both the unguarded and
  guarded `kgraph-host-functions` forms share one implementation."
  [store]
  {'kgraph-assert!
   (fn [instance args]
     (swap! store kgraph/assert-datom
            (edn/read-string (read-str instance (aget args 0) (aget args 1))))
     0)
   'kgraph-retract!
   (fn [instance args]
     (swap! store kgraph/retract-datom
            (edn/read-string (read-str instance (aget args 0) (aget args 1))))
     0)
   'kgraph-get-objects
   (fn [instance args]
     (let [e (edn/read-string (read-str instance (aget args 0) (aget args 1)))
           bs (.getBytes (pr-str (kgraph/get-objects @store e)) "UTF-8")]
       (write-bytes! instance (aget args 2) (aget args 3) bs)))
   'kgraph-query
   (fn [instance args]
     (let [q (edn/read-string (read-str instance (aget args 0) (aget args 1)))
           bs (.getBytes (pr-str (kgraph/query @store q)) "UTF-8")]
       (write-bytes! instance (aget args 2) (aget args 3) bs)))})

(def ^:private kgraph-op-specs
  "op symbol -> the (module \"kotoba\") host-import wire shape for one
  kgraph-* op (field name, Chicory ValTypes) — mirrors the :params/:result
  of the matching entry in kotoba.runtime/host-imports."
  {'kgraph-assert! {:field "kgraph_assert"
                    :params [ValType/I32 ValType/I32] :result ValType/I32}
   'kgraph-retract! {:field "kgraph_retract"
                     :params [ValType/I32 ValType/I32] :result ValType/I32}
   'kgraph-get-objects {:field "kgraph_get_objects"
                        :params [ValType/I32 ValType/I32 ValType/I32 ValType/I32]
                        :result ValType/I32}
   'kgraph-query {:field "kgraph_query"
                 :params [ValType/I32 ValType/I32 ValType/I32 ValType/I32]
                 :result ValType/I32}})

(defn- guard-kgraph-call
  "Wrap EFFECT — one kgraph-* OP's raw (fn [instance args] -> long) body —
  behind kotoba.lang.capability-host/guard-call, deriving CACAO-style grants
  and a local policy from POLICY via kotoba.host-providers/policy-grants and
  kotoba.host-providers/local-policy — the SAME derivation
  kotoba.host-providers/host-call uses for the CLJ-interpreter path, reused
  rather than reinvented. A denied call throws BEFORE EFFECT ever touches
  STORE or guest memory (fail closed, matching host-providers/host-call's
  contract); every attempt — granted, denied, or a handler error — is
  receipted via RECORD! when supplied (OPTS may also carry :now, an ISO date
  string defaulting to today)."
  [op effect {:keys [policy record! now]}]
  (let [kind (get runtime/op->kind op)
        grants (host-providers/policy-grants policy)
        allow (host-providers/local-policy policy)
        now (or now (str (java.time.LocalDate/now)))]
    (fn [instance args]
      (let [outcome (capability-host/guard-call
                     {:call (keyword "kotoba.wasm" (name op))
                      :requested (capability-values/make-cap kind :any)
                      :cacao-grants grants
                      :local-policy allow
                      :now now
                      :record! record!
                      :handler (fn [_concrete] (effect instance args))})]
        (if (:kotoba.host/ok? outcome)
          (:kotoba.host/result outcome)
          (throw (ex-info "wasm kgraph host call denied by capability guard"
                          {:kotoba.host/denied (:kotoba.host/denied outcome)
                           :kotoba.host/call op
                           :kotoba.host/receipt (:kotoba.host/receipt outcome)})))))))

(defn kgraph-host-functions
  "The kgraph-* host imports, backed by STORE (an atom of `kotoba.kgraph`
  datom vectors — shared across calls within one Instance, fresh per
  test/run unless the caller deliberately reuses it).

  1-arg form (UNGUARDED, the pre-existing behavior): every call performs its
  effect unconditionally, relying entirely on the static compile-time
  capability gate (kotoba.runtime/check) having refused to emit this import
  under a policy that didn't allow it. That gate is real, but it only holds
  if the bytes reaching `instantiate` were actually produced by `check`
  under the policy this run intends — nothing at THIS boundary verifies
  that, so arbitrary/reused/tampered `.wasm` bytes get a free pass here.
  Kept as the default so existing callers (this namespace's own round-trip
  test, any caller not ready to supply a policy) are unaffected.

  2-/3-arg forms (GUARDED): every kgraph-* call is dispatched through
  `guard-kgraph-call` — a real fail-closed per-call capability check derived
  from POLICY, exactly mirroring kotoba.host-providers/host-call for the
  interpreter path. A denied call throws before STORE or guest memory is
  touched. OPTS (3-arg form) may carry :record!/:now, see
  `guard-kgraph-call`."
  ([store]
   (mapv (fn [[op effect]]
           (let [{:keys [field params result]} (get kgraph-op-specs op)]
             (host-fn field params result effect)))
         (kgraph-effects store)))
  ([store policy] (kgraph-host-functions store policy nil))
  ([store policy opts]
   (mapv (fn [[op effect]]
           (let [{:keys [field params result]} (get kgraph-op-specs op)]
             (host-fn field params result
                      (guard-kgraph-call op effect (assoc opts :policy policy)))))
         (kgraph-effects store))))

(defn instantiate
  "Parse WASM-BYTES and build a Chicory Instance with EXTRA-HOST-FNS (a seq
  of HostFunction, e.g. `kgraph-host-functions`) plus a real `has_capability`
  host function bound (see `has-capability-fn`) and a fuel-limited
  ExecutionListener bound (see `fuel-listener`). POLICY (same EDN vocabulary
  throughout this repo: :kotoba.policy/capabilities, plus :kotoba.policy/fuel
  for the instruction budget) governs BOTH what `has-capability?` answers
  true for during this run and the fuel budget; no POLICY means nothing is
  granted (fail closed) and the default fuel limit applies — this is a
  DELIBERATE change from the previous always-grant stub, not an oversight.
  Every import the module actually declares must be satisfied (Chicory links
  by (module, field) name, not declaration order) or `.build` throws."
  ([wasm-bytes extra-host-fns] (instantiate wasm-bytes extra-host-fns nil))
  ([wasm-bytes extra-host-fns policy]
   (let [imports (-> (ImportValues/builder)
                     (.addFunction (into-array ImportFunction
                                               (cons (has-capability-fn policy) extra-host-fns)))
                     .build)
         module (Parser/parse ^bytes wasm-bytes)]
     (-> (Instance/builder module)
         (.withImportValues imports)
         (.withUnsafeExecutionListener (fuel-listener (fuel-limit policy)))
         .build))))

(defn call-main
  "Invoke an already-built Instance's 0-arity exported `main` and return its
  single i32/i64 result as a long."
  [instance]
  (aget ^longs (.apply (.export instance "main") (long-array 0)) 0))

(defn run-main
  "Instantiate WASM-BYTES with EXTRA-HOST-FNS under POLICY (see
  `instantiate`) and execute the exported 0-arity `main`, returning its
  single i32/i64 result as a long."
  ([wasm-bytes extra-host-fns] (run-main wasm-bytes extra-host-fns nil))
  ([wasm-bytes extra-host-fns policy]
   (call-main (instantiate wasm-bytes extra-host-fns policy))))

(defn read-memory-string
  "Read a UTF-8 string of LEN bytes at PTR out of INSTANCE's memory — for
  reading a result a `main` wrote into a caller-provided buffer and returned
  the pointer/length of (tests use this to inspect kgraph_query output)."
  [instance ptr len]
  (read-str instance ptr len))
