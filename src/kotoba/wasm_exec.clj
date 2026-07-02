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
  prove — not just assert — that emitted modules run."
  (:require [clojure.edn :as edn]
            [kotoba.kgraph :as kgraph])
  (:import (com.dylibso.chicory.runtime HostFunction ImportFunction ImportValues
                                        Instance WasmFunctionHandle)
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

(defn has-capability-fn
  "Permissive `has_capability` stub: every kind is granted. The static
  capability GATE already ran at `check`/`wasm emit` time (denied programs
  never reach this far); this only backs the runtime `has-capability?`
  branch some sources also take at execution time."
  []
  (host-fn "has_capability" [ValType/I32] ValType/I32
           (fn [_instance _args] 1)))

(defn kgraph-host-functions
  "The kgraph-* host imports, backed by STORE (an atom of `kotoba.kgraph`
  datom vectors — shared across calls within one Instance, fresh per test/run
  unless the caller deliberately reuses it)."
  [store]
  [(host-fn "kgraph_assert" [ValType/I32 ValType/I32] ValType/I32
            (fn [instance args]
              (swap! store kgraph/assert-datom
                     (edn/read-string (read-str instance (aget args 0) (aget args 1))))
              0))
   (host-fn "kgraph_retract" [ValType/I32 ValType/I32] ValType/I32
            (fn [instance args]
              (swap! store kgraph/retract-datom
                     (edn/read-string (read-str instance (aget args 0) (aget args 1))))
              0))
   (host-fn "kgraph_get_objects" [ValType/I32 ValType/I32 ValType/I32 ValType/I32] ValType/I32
            (fn [instance args]
              (let [e (edn/read-string (read-str instance (aget args 0) (aget args 1)))
                    bs (.getBytes (pr-str (kgraph/get-objects @store e)) "UTF-8")]
                (write-bytes! instance (aget args 2) (aget args 3) bs))))
   (host-fn "kgraph_query" [ValType/I32 ValType/I32 ValType/I32 ValType/I32] ValType/I32
            (fn [instance args]
              (let [q (edn/read-string (read-str instance (aget args 0) (aget args 1)))
                    bs (.getBytes (pr-str (kgraph/query @store q)) "UTF-8")]
                (write-bytes! instance (aget args 2) (aget args 3) bs))))])

(defn instantiate
  "Parse WASM-BYTES and build a Chicory Instance with EXTRA-HOST-FNS (a seq of
  HostFunction, e.g. `kgraph-host-functions`) plus the permissive capability
  stub bound. Every import the module actually declares must be satisfied
  (Chicory links by (module, field) name, not declaration order) or `.build`
  throws."
  [wasm-bytes extra-host-fns]
  (let [imports (-> (ImportValues/builder)
                    (.addFunction (into-array ImportFunction
                                              (cons (has-capability-fn) extra-host-fns)))
                    .build)
        module (Parser/parse ^bytes wasm-bytes)]
    (-> (Instance/builder module) (.withImportValues imports) .build)))

(defn call-main
  "Invoke an already-built Instance's 0-arity exported `main` and return its
  single i32/i64 result as a long."
  [instance]
  (aget ^longs (.apply (.export instance "main") (long-array 0)) 0))

(defn run-main
  "Instantiate WASM-BYTES with EXTRA-HOST-FNS and execute the exported
  0-arity `main`, returning its single i32/i64 result as a long."
  [wasm-bytes extra-host-fns]
  (call-main (instantiate wasm-bytes extra-host-fns)))

(defn read-memory-string
  "Read a UTF-8 string of LEN bytes at PTR out of INSTANCE's memory — for
  reading a result a `main` wrote into a caller-provided buffer and returned
  the pointer/length of (tests use this to inspect kgraph_query output)."
  [instance ptr len]
  (read-str instance ptr len))
