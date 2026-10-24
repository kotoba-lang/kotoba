(ns browser-parity
  "Does the emitted module agree with the interpreter?

  `schema-digest` needs no capability -- it builds S as a document and hashes
  it -- so it can be called on the browser host with no dataspace stub, and it
  exercises exactly the operations that were broken on ClojureScript: document
  construction and `document-sha256`. If the wasm module and the reference
  interpreter return the same 64 hex characters, the two backends agree on a
  value.

  WHAT THIS DOES NOT SHOW. It does not exercise the dataspace capability on
  wasm: doing that needs a provider written against the browser host's own
  value representation, and there is not one here. So this says the module
  instantiates and that the two backends agree on S's identity -- it does not
  say the kernel ADMITS the same way on both. Conformance still runs only on
  the interpreter.

  It discriminates: pointed at a module compiled from a different S, the
  digests differ and the check fails (measured 2026-08-31 by renaming one
  entity type). A check that only asserted `is a sha256` would have passed."
  (:require [kotoba.kir.admission :as admission]
            [kotoba.sema :as sema]
            [kotoba.kir :as ir]
            [provider.dataspace :as ds]
            [kotoba.compiler.reference-runtime :as runtime]
            ["node:fs" :as fs]))

(def env (.-env js/process))
(def source (.readFileSync fs (aget env "OAK_SOURCE") "utf8"))
(def wasm-path (aget env "OAK_WASM"))
(def host-path (aget env "OAK_BROWSER_HOST"))

(defn- interpreter-digest []
  (let [hir (sema/analyze source)
        _ (admission/check hir {:allow #{[:cap/call (js/BigInt 24)]}})
        rt (runtime/instantiate (ir/lower hir)
                                {:allow #{24} :providers {24 (ds/provider)}})]
    ((:invoke rt) 'schema-digest [])))

(defn- check [label ok? detail]
  (println (if ok? "PASS" "FAIL") label (if ok? "" (pr-str detail)))
  (when-not ok? (set! (.-exitCode js/process) 1)))

(-> (js/import host-path)
    (.then
     (fn [host]
       (-> ((.-instantiateKotoba host)
            (.readFileSync fs wasm-path)
            #js {:allowCapabilities #js [24]
                 :typedCapCall (fn [& _]
                                 (throw (js/Error. "schema-digest must not call out")))})
           (.then
            (fn [instance]
              (let [ex (.-exports (.-instance instance))
                    wasm-digest ((aget ex "schema-digest"))
                    interp (try (interpreter-digest)
                                (catch :default e (str "THREW " (.-message e))))]
                (check "the module instantiates on the browser host" (some? ex) (js-keys ex))
                (check "the wasm digest is a sha256"
                       (and (string? wasm-digest) (= 64 (count wasm-digest)))
                       wasm-digest)
                (check "wasm and the interpreter agree on the schema digest"
                       (= wasm-digest interp)
                       {:wasm wasm-digest :interpreter interp})
                (println "digest:" wasm-digest))))
           (.catch (fn [e]
                     (check "the module instantiates on the browser host" false
                            (or (.-message e) e)))))))
    (.catch (fn [e] (println "FAIL could not load the browser host" (.-message e))
              (set! (.-exitCode js/process) 1))))
