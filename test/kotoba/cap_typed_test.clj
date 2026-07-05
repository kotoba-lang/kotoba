(ns kotoba.cap-typed-test
  "S4b typed capability parameters + full compiled threading: `^{:cap <kind>}`
  params are statically checked (cap-typed args only, kind consistency,
  interprocedural effect rows), lower to i64 handle slots in wasm, and cap
  handles flow through user-defined function calls end-to-end
  (main -> outer -> inner -> host import)."
  (:require [clojure.java.io :as io]
            [clojure.java.shell :as shell]
            [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime])
  (:import [java.io File]))

;; wasm emit/run require a mandatory package-admission gate (F-001);
;; every dispatch call reaching those subcommands needs an admitted lock.
(def positive-lock "test/fixtures/package/positive-lock.edn")
(def trust "test/fixtures/package/trust.edn")

(defn temp-file
  [prefix suffix content]
  (let [file (doto (File/createTempFile prefix suffix)
               (.deleteOnExit))]
    (spit file content)
    (.getPath file)))

(defn temp-edn-file
  [content]
  (temp-file "kotoba-cap-typed-policy" ".edn" (pr-str content)))

(def demo-policy
  {:kotoba.policy/capabilities #{:ledger/append}
   :kotoba.policy/capability-resources {:ledger/append #{"ledger:main"}}})

(def wide-policy
  "Grants ledger AND notify so kind-mismatch cases fail on the typed gate,
  not on :capability-not-granted."
  {:kotoba.policy/capabilities #{:ledger/append :notify/show}})

(defn check-problems
  [source policy]
  (let [result (launcher/dispatch ["check"
                                   (temp-file "kotoba-cap-typed" ".kotoba" source)
                                   "--policy" (temp-edn-file policy)
                                   "--json"])]
    {:ok? (:kotoba.cli/ok? result)
     :code (:kotoba.cli/code result)
     :problems (get-in result [:kotoba.cli/data :kotoba.runtime/result
                               :kotoba.runtime/problems])}))

(deftest typed-cap-param-lowers-to-i64
  (let [forms (runtime/read-forms
               (str "(defn ^{:i64 true} use-ledger"
                    " [^{:cap :host/ledger-append} c ^:i64 code] "
                    "(host-i64-roundtrip-with c code))")
               :kotoba)
        [def-entry] (runtime/function-defs forms)]
    (is (= [:i64 :i64] (runtime/function-param-types def-entry)))
    (is (= :host/ledger-append
           (runtime/cap-param-kind (first (:params (second def-entry))))))))

(deftest typed-param-happy-path-interpreter-two-level-threading
  (let [result (launcher/dispatch ["run" "src/demo_cap_threading.kotoba"
                                   "--policy" "src/demo_cap_threading_policy.edn"
                                   "--json"])
        receipts (get-in result [:kotoba.cli/data :kotoba.host/receipts])
        [acquire-receipt use-receipt] receipts]
    (is (true? (:kotoba.cli/ok? result)))
    (is (= :run/completed (:kotoba.cli/code result)))
    ;; main acquires, outer bumps 41 -> 42, inner threads the handle to the
    ;; host import which echoes the code.
    (is (= 42 (get-in result [:kotoba.cli/data :kotoba.runtime/result
                              :kotoba.runtime/value])))
    (testing "receipts show the SAME handle at acquire and at use, same concrete cap"
      (is (= 2 (count receipts)))
      (is (= :cap/acquire (:receipt/call acquire-receipt)))
      (is (= :kotoba.host/host-i64-roundtrip-with (:receipt/call use-receipt)))
      (is (= [:ok :ok] (mapv :receipt/outcome receipts)))
      (is (= 1 (:receipt/cap-handle acquire-receipt)))
      (is (= (:receipt/cap-handle acquire-receipt)
             (:receipt/cap-handle use-receipt)))
      (is (= (:receipt/cap acquire-receipt) (:receipt/cap use-receipt)))
      (is (= :host/ledger-append
             (get-in use-receipt [:receipt/cap :cap/kind])))))
  (testing "the same source passes `check` (typed gate + effect rows green)"
    (let [checked (launcher/dispatch ["check" "src/demo_cap_threading.kotoba"
                                      "--policy" "src/demo_cap_threading_policy.edn"
                                      "--json"])]
      (is (true? (:kotoba.cli/ok? checked)))
      (is (= :check/valid (:kotoba.cli/code checked))))))

(deftest untyped-arg-to-with-op-rejected-statically
  (let [{:keys [ok? code problems]}
        (check-problems (str "(ns demo-forged)\n"
                             "(defn main []\n"
                             "  (host-i64-roundtrip-with (i64 7) (i64 41)))\n")
                        demo-policy)]
    (is (false? ok?))
    (is (= :check/invalid code))
    (is (= [{:kotoba.runtime/problem :cap-arg-not-capability
             :kotoba.runtime/fn "main"
             :kotoba.runtime/op "host-i64-roundtrip-with"
             :kotoba.runtime/arg "(i64 7)"}]
           problems)))
  (testing "an untyped value into a callee's cap-typed param is also rejected"
    (let [{:keys [ok? problems]}
          (check-problems (str "(ns demo-forged2)\n"
                               "(defn ^{:i64 true} inner"
                               " [^{:cap :host/ledger-append} c ^:i64 code]\n"
                               "  (host-i64-roundtrip-with c code))\n"
                               "(defn ^{:i64 true} main []\n"
                               "  (inner (i64 7) (i64 41)))\n")
                          demo-policy)]
      (is (false? ok?))
      (is (= :cap-arg-not-capability
             (:kotoba.runtime/problem (first problems))))
      (is (= "inner" (:kotoba.runtime/op (first problems)))))))

(deftest kind-mismatch-rejected-statically
  (testing "a cap-typed param of the wrong kind presented to <op>-with"
    (let [{:keys [ok? problems]}
          (check-problems (str "(ns demo-mismatch)\n"
                               "(defn ^{:i64 true} f [^{:cap :host/notify} c]\n"
                               "  (host-i64-roundtrip-with c (i64 1)))\n"
                               "(defn ^{:i64 true} main []\n"
                               "  (let [c (cap-acquire :host/notify \"note:main\")]\n"
                               "    (f c)))\n")
                          wide-policy)]
      (is (false? ok?))
      (is (= [{:kotoba.runtime/problem :cap-kind-mismatch
               :kotoba.runtime/fn "f"
               :kotoba.runtime/op "host-i64-roundtrip-with"
               :kotoba.runtime/expected :host/ledger-append
               :kotoba.runtime/actual :host/notify}]
             problems))))
  (testing "an acquired cap of the wrong kind passed to a callee's typed param"
    (let [{:keys [ok? problems]}
          (check-problems (str "(ns demo-mismatch2)\n"
                               "(defn ^{:i64 true} inner"
                               " [^{:cap :host/ledger-append} c ^:i64 code]\n"
                               "  (host-i64-roundtrip-with c code))\n"
                               "(defn ^{:i64 true} main []\n"
                               "  (let [c (cap-acquire :host/notify \"note:main\")]\n"
                               "    (inner c (i64 41))))\n")
                          wide-policy)]
      (is (false? ok?))
      (is (= :cap-kind-mismatch
             (:kotoba.runtime/problem (first problems))))
      (is (= "inner" (:kotoba.runtime/op (first problems))))
      (is (= :host/ledger-append (:kotoba.runtime/expected (first problems))))
      (is (= :host/notify (:kotoba.runtime/actual (first problems))))))
  (testing "an unknown kind on a cap-typed param is rejected"
    (let [{:keys [ok? problems]}
          (check-problems (str "(ns demo-unknown-kind)\n"
                               "(defn f [^{:cap :host/nope} c] c)\n"
                               "(defn main [] 0)\n")
                          demo-policy)]
      (is (false? ok?))
      (is (= [{:kotoba.runtime/problem :unknown-capability-kind
               :kotoba.runtime/fn "f"
               :kotoba.runtime/kind ":host/nope"}]
             problems)))))

(deftest effect-under-declaration-through-one-level-of-calls-rejected
  (testing "a caller's declared row must cover what its callee requires"
    (let [{:keys [ok? problems]}
          (check-problems (str "(ns demo-effect-call)\n"
                               "(defn ^{:i64 true} helper []\n"
                               "  (let [c (cap-acquire :host/ledger-append \"ledger:main\")]\n"
                               "    (host-i64-roundtrip-with c (i64 41))))\n"
                               "(defn ^{:i64 true :effects #{}} main []\n"
                               "  (helper))\n")
                          demo-policy)]
      (is (false? ok?))
      (is (= [{:kotoba.runtime/problem :cap-effect-under-declared
               :kotoba.runtime/fn "main"
               :kotoba.runtime/missing #{:host/ledger-append}}]
             problems))))
  (testing "a cap-typed param alone puts its kind into the fn's required effects"
    (let [{:keys [ok? problems]}
          (check-problems (str "(ns demo-effect-param)\n"
                               "(defn ^{:i64 true :effects #{}} f"
                               " [^{:cap :host/ledger-append} c] c)\n"
                               "(defn main [] 0)\n")
                          demo-policy)]
      (is (false? ok?))
      (is (= [{:kotoba.runtime/problem :cap-effect-under-declared
               :kotoba.runtime/fn "f"
               :kotoba.runtime/missing #{:host/ledger-append}}]
             problems))))
  (testing "covering rows through the call graph are accepted (threading demo)"
    (let [{:keys [ok? code]}
          (check-problems (slurp "src/demo_cap_threading.kotoba") demo-policy)]
      (is (true? ok?))
      (is (= :check/valid code)))))

(deftest wasm-emit-threads-cap-handles-through-user-fn-calls
  (let [forms (runtime/read-file "src/demo_cap_threading.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms nil)
        output (doto (File/createTempFile "kotoba-demo-cap-threading" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_cap_threading.kotoba"
                                    "--policy" "src/demo_cap_threading_policy.edn"
                                    "--output" (.getPath output)
                                    "--json" "--package-lock" positive-lock "--trust" trust])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i64 (:kotoba.wasm/result-type wasm)))
    (is (= 3 (:kotoba.wasm/function-count wasm)))
    (testing "import section shape: cap_acquire + host_i64_roundtrip_with"
      (is (= 2 (:kotoba.wasm/import-count wasm)))
      (is (= [{:module "kotoba"
               :field "cap_acquire"
               :params [:i32 :i32 :i32]
               :result :i64}
              {:module "kotoba"
               :field "host_i64_roundtrip_with"
               :capability "ledger/append"
               :params [:i64 :i64]
               :result :i64}]
             (:kotoba.wasm/imports wasm))))
    (is (= 1 (:kotoba.wasm/data-segment-count wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= :wasm/binary-emitted (:kotoba.cli/code emitted)))
    (is (= 2 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff)
                 (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

;; ---------------------------------------------------------------------------
;; Node instantiation smoke

(def node-cap-host-script
  "Host-side cap map matching the docs/lang/gates.md cap-passing gate:
  cap_acquire validates kind id 201 + the literal resource and issues a
  handle; host_i64_roundtrip_with echoes the code for a known handle and
  returns -1 for anything it never issued (fail closed)."
  (str "const fs = require('fs');\n"
       "let memory;\n"
       "const caps = new Map(); let next = 1n;\n"
       "const text = (ptr, len) => new TextDecoder().decode(new Uint8Array(memory.buffer, ptr, len));\n"
       "const imports = { kotoba: {\n"
       "  cap_acquire: (kindId, resPtr, resLen) => {\n"
       "    if (kindId !== 201 || text(resPtr, resLen) !== 'ledger:main') return 0n;\n"
       "    const handle = next++; caps.set(handle, { kind: kindId }); return handle;\n"
       "  },\n"
       "  host_i64_roundtrip_with: (cap, code) => caps.has(cap) ? code : -1n\n"
       "}};\n"
       "WebAssembly.instantiate(fs.readFileSync(process.argv[2]), imports).then(({instance}) => {\n"
       "  memory = instance.exports.memory;\n"
       "  console.log(instance.exports.main().toString());\n"
       "});\n"))

(defn node-available?
  []
  (try
    (zero? (:exit (shell/sh "node" "--version")))
    (catch Exception _ false)))

(defn node-run-main
  "Instantiate WASM-PATH under the cap-map host and return main()'s printed
  i64 as a string."
  [wasm-path]
  (let [script (temp-file "kotoba-cap-host" ".js" node-cap-host-script)
        {:keys [exit out err]} (shell/sh "node" script wasm-path)]
    (is (zero? exit) (str "node failed: " err))
    (str/trim out)))

(deftest node-instantiation-smoke-threading-and-forged-variant
  (if-not (node-available?)
    (println "kotoba.cap-typed-test: node unavailable, skipping instantiation smoke")
    (let [output (doto (File/createTempFile "kotoba-demo-cap-threading" ".wasm")
                   (.deleteOnExit))
          emitted (launcher/dispatch ["wasm" "emit" "src/demo_cap_threading.kotoba"
                                      "--policy" "src/demo_cap_threading_policy.edn"
                                      "--output" (.getPath output)
                                      "--json" "--package-lock" positive-lock "--trust" trust])]
      (is (:kotoba.cli/ok? emitted))
      (testing "two-level threading returns the expected value under the cap-map host"
        (is (= "42" (node-run-main (.getPath output)))))
      (testing "a forged handle constant inside a variant module fails closed at the host binding"
        ;; The launcher's own emit path rejects the forge statically...
        (let [forged-source (str "(ns demo-forged-wasm)\n"
                                 "(defn ^{:i64 true} main []\n"
                                 "  (host-i64-roundtrip-with (i64 7) (i64 41)))\n")
              forged-path (temp-file "kotoba-cap-forged" ".kotoba" forged-source)
              rejected (launcher/dispatch ["wasm" "emit" forged-path
                                           "--policy" (temp-edn-file demo-policy)
                                           "--json" "--package-lock" positive-lock "--trust" trust])]
          (is (false? (:kotoba.cli/ok? rejected)))
          (is (= :wasm/check-failed (:kotoba.cli/code rejected)))
          (is (= :cap-arg-not-capability
                 (get-in rejected [:kotoba.cli/data :kotoba.runtime/result
                                   :kotoba.runtime/problems 0
                                   :kotoba.runtime/problem])))
          ;; ...and even a module produced by a hostile front end that skips
          ;; the checker (runtime/wasm-binary directly) is refused by the
          ;; host-side cap map: the unissued handle earns -1.
          (let [forms (runtime/read-forms forged-source :kotoba)
                wasm (runtime/wasm-binary forms nil)
                forged-out (doto (File/createTempFile "kotoba-demo-cap-forged" ".wasm")
                             (.deleteOnExit))]
            (is (:kotoba.wasm/ok? wasm))
            (with-open [out (io/output-stream forged-out)]
              (.write out ^bytes (:kotoba.wasm/binary wasm)))
            (is (= "-1" (node-run-main (.getPath forged-out))))))))))
