(ns kotoba.launcher-test
  (:require [clojure.data.json :as json]
            [clojure.edn :as edn]
            [clojure.test :refer [deftest is run-tests]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime]))

(deftest delegates-check-to-cljc-authority
  (let [result (launcher/dispatch ["check" "--kind" "cli-contract" "--json"])]
    (is (:kotoba.cli/ok? result))
    (is (= :contract/valid (:kotoba.cli/code result)))
    (is (true? (get (json/read-str (launcher/render-result result true))
                    "kotoba.cli/ok?")))))

(deftest side-effecting-commands-stay-data
  (let [result (launcher/dispatch ["deploy" "--manifest" "package-manifest.edn" "--target" "dev"])]
    (is (:kotoba.cli/ok? result))
    (is (= :command/planned (:kotoba.cli/code result)))
    (is (= :adapter-required (get-in result [:kotoba.cli/data :host-action])))))

(deftest returns-nonzero-for-unknown-command
  (let [result (launcher/dispatch ["unknown"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= 1 (launcher/result->exit result)))))

(deftest loads-safe-analyzer-fact-seed-from-clj-resources
  (let [seed (launcher/safe-analyzer-fact-classification)]
    (is (= "kotoba.selfhost.safe-analyzer-facts.v0" (:schema seed)))
    (is (launcher/safe-analyzer-fact-classified? :non-executable-forms "defmacro"))
    (is (launcher/safe-analyzer-fact-classified? :numeric-result-ops "Math/sqrt"))
    (is (launcher/safe-analyzer-fact-classified? :effect-ops "kgraph-query"))
    (is (launcher/safe-analyzer-fact-classified? :user-call-excluded-ops "llm-infer"))
    (is (not (launcher/safe-analyzer-fact-classified? :effect-ops "pure-helper")))))

(deftest loads-canonical-selfhost-seeds-from-clj-resources
  (let [seeds (launcher/selfhost-seeds)]
    (is (= (set (map keyword launcher/selfhost-seed-names))
           (set (keys seeds))))
    (is (= "aiueos.provider-catalog.v0"
           (:schema (:aiueos_provider_catalog seeds))))
    (is (= 8 (get-in seeds [:aiueos_provider_catalog :oracle-exports "provider-family-count"])))
    (is (= 13 (count (get-in seeds [:aiueos_provider_catalog :digest :commands]))))
    (is (= 13508 (get-in seeds [:plugin_contract :exports "registry-schema-digest"])))
    (is (= 52053
           (get (launcher/contract-exports (:runtime_contract seeds) :android)
                "android-runtime-command-plan-digest")))
    (is (= 4
           (get (launcher/contract-exports (:release_target_contract seeds) :android)
                "android-env-count")))
    (is (= 25
           (get-in seeds [:shell_evidence_profile :oracle-exports "required-command-count"])))))

(deftest classifies-kotoba-and-cljc-source-inputs
  (let [contract (launcher/source-contract)]
    (is (= "kotoba.lang.source-contract.v0" (:schema contract)))
    (is (= :kotoba (launcher/source-kind contract "src/app.kotoba")))
    (is (= :clj (launcher/source-kind contract "src/app.clj")))
    (is (= :cljc (launcher/source-kind contract "src/app.cljc")))
    (is (nil? (launcher/source-kind contract "src/app.cljs")))
    (is (= :edn (launcher/source-kind contract "policy.edn")))
    (is (nil? (launcher/source-kind contract "README.md")))))

(deftest builds-source-dispatch-plan-for-cljc-and-kotoba
  (is (= {:kotoba.source/path "src/app.kotoba"
          :kotoba.source/kind :kotoba
          :kotoba.source/extension ".kotoba"
          :kotoba.source/reader-target :kotoba
          :kotoba.source/canonical? true
          :kotoba.source/portable? false
          :kotoba.source/data? false
          :kotoba.source/safe-gate-required? true}
         (launcher/source-plan "src/app.kotoba")))
  (is (= :kotoba (:kotoba.source/reader-target
                  (launcher/source-plan "src/shared.cljc"))))
  (is (= :cljs (:kotoba.source/reader-target
                (launcher/source-plan "src/shared.cljc" :cljs))))
  (is (= :cljc (:kotoba.source/kind
                (launcher/source-plan "src/shared.cljc" :clj))))
  (is (= false (:kotoba.source/safe-gate-required?
                (launcher/source-plan "manifest.edn"))))
  (is (thrown-with-msg? clojure.lang.ExceptionInfo
                        #"unsupported Kotoba source extension"
                        (launcher/source-plan "notes.md"))))

(deftest normalizes-source-argv-for-cljc-authority
  (is (= ["run" "src/shared.cljc" "--json" "--reader-target" "kotoba"]
         (launcher/normalize-source-argv ["run" "src/shared.cljc" "--json"])))
  (is (= ["run" "src/shared.cljc" "--reader-target" "cljs" "--json"]
         (launcher/normalize-source-argv ["run" "src/shared.cljc" "--reader-target" "cljs" "--json"])))
  (is (= ["check" "src/shared.cljc" "--target" "clj" "--json"]
         (launcher/normalize-source-argv ["check" "src/shared.cljc" "--target" "clj" "--json"])))
  (is (= "src/app.kotoba"
         (launcher/first-source-arg ["check" "--policy" "policy.edn" "src/app.kotoba" "--json"])))
  (is (= ["deploy" "--manifest" "package-manifest.edn" "--target" "dev"]
         (launcher/normalize-source-argv ["deploy" "--manifest" "package-manifest.edn" "--target" "dev"]))))

(deftest annotates-run-and-check-results-with-source-plan
  (let [run-result (launcher/dispatch ["run" "src/shared.cljc" "--reader-target" "cljs" "--json"])
        check-result (launcher/dispatch ["check" "src/app.kotoba" "--json"])
        deploy-result (launcher/dispatch ["deploy" "--manifest" "package-manifest.edn" "--target" "dev"])]
    (is (= :cljc (get-in run-result [:kotoba.cli/data :kotoba.launcher/source-plan
                                     :kotoba.source/kind])))
    (is (= :cljs (get-in run-result [:kotoba.cli/data :kotoba.launcher/source-plan
                                     :kotoba.source/reader-target])))
    (is (= :kotoba (get-in check-result [:kotoba.cli/data :kotoba.launcher/source-plan
                                         :kotoba.source/kind])))
    (is (= :kotoba (get-in check-result [:kotoba.cli/data :kotoba.launcher/source-plan
                                         :kotoba.source/reader-target])))
    (is (= ["check" "src/app.kotoba" "--json" "--reader-target" "kotoba"]
           (get-in check-result [:kotoba.cli/data :kotoba.launcher/authority-request
                                 :kotoba.launcher/normalized-argv])))
    (is (= "kotoba-lang/kotoba-lang"
           (get-in check-result [:kotoba.cli/data :kotoba.launcher/authority-request
                                 :kotoba.launcher/authority])))
    (is (true? (get-in check-result [:kotoba.cli/data :kotoba.launcher/authority-request
                                     :kotoba.launcher/reader-target-added?])))
    (is (false? (get-in run-result [:kotoba.cli/data :kotoba.launcher/authority-request
                                    :kotoba.launcher/reader-target-added?])))
    (is (nil? (get-in deploy-result [:kotoba.cli/data :kotoba.launcher/source-plan])))))

(deftest selfhost-list-and-check-are-clj-launcher-commands
  (let [list-result (launcher/dispatch ["selfhost" "list" "--json"])
        check-result (launcher/dispatch ["selfhost" "check" "--json"])
        unknown-result (launcher/dispatch ["selfhost" "wat"])]
    (is (:kotoba.cli/ok? list-result))
    (is (= :selfhost/listed (:kotoba.cli/code list-result)))
    (is (= 17 (get-in list-result [:kotoba.cli/data :kotoba.selfhost/seed-count])))
    (is (= "kotoba.selfhost.safe-analyzer-facts.v0"
           (some (fn [seed]
                   (when (= :safe_analyzer_facts (:kotoba.selfhost/name seed))
                     (:kotoba.selfhost/schema seed)))
                 (get-in list-result [:kotoba.cli/data :kotoba.selfhost/seeds]))))
    (is (:kotoba.cli/ok? check-result))
    (is (= :selfhost/valid (:kotoba.cli/code check-result)))
    (is (= [] (get-in check-result [:kotoba.cli/data :kotoba.selfhost/problems])))
    (is (false? (:kotoba.cli/ok? unknown-result)))
    (is (= :selfhost/unknown-command (:kotoba.cli/code unknown-result)))))

(deftest run-and-check-existing-source-through-clj-runtime
  (let [kotoba-check (launcher/dispatch ["check" "src/demo.kotoba" "--json"])
        kotoba-run (launcher/dispatch ["run" "src/demo.kotoba" "--json"])
        cljc-run (launcher/dispatch ["run" "src/demo.cljc" "--json"])
        cljs-run (launcher/dispatch ["run" "src/demo.cljc" "--reader-target" "cljs" "--json"])]
    (is (:kotoba.cli/ok? kotoba-check))
    (is (= :check/valid (:kotoba.cli/code kotoba-check)))
    (is (= :run/completed (:kotoba.cli/code kotoba-run)))
    (is (= 42 (get-in kotoba-run [:kotoba.cli/data :kotoba.runtime/result
                                  :kotoba.runtime/value])))
    (is (= 123 (get-in cljc-run [:kotoba.cli/data :kotoba.runtime/result
                                 :kotoba.runtime/value])))
    (is (= 30 (get-in cljs-run [:kotoba.cli/data :kotoba.runtime/result
                                :kotoba.runtime/value])))
    (is (= "kotoba.runtime.edn-ir.v0"
           (get-in kotoba-check [:kotoba.cli/data :kotoba.runtime/result
                                 :kotoba.runtime/ir :schema])))))

(deftest shell-command-is-owned-by-kotoba-shell
  (let [result (launcher/dispatch ["shell" "native-host" "check" "--target" "macos"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :command/unknown (:kotoba.cli/code result)))
    (is (= :shell (get-in result [:kotoba.cli/data :command])))
    (is (nil? (get-in result [:kotoba.cli/data :kotoba.shell/deprecated-shim?])))))

(deftest wasm-emit-exposes-current-binary-emitter
  (let [forms (runtime/read-file "src/demo.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo" ".wasm")
                 (.deleteOnExit))
        result (launcher/dispatch ["wasm" "emit" "src/demo.kotoba" "--json"
                                   "--output" (.getPath output)])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= [0 97 115 109 1 0 0 0]
           (mapv #(bit-and % 0xff) (take 8 (:kotoba.wasm/binary wasm)))))
    (is (:kotoba.cli/ok? result))
    (is (= :wasm/binary-emitted (:kotoba.cli/code result)))
    (is (= true (get-in result [:kotoba.cli/data :kotoba.wasm/binary?])))
    (is (= :webassembly/module
           (get-in result [:kotoba.cli/data :kotoba.wasm/artifact-kind])))
    (is (= "main" (get-in result [:kotoba.cli/data :kotoba.wasm/export])))
    (is (= :i32 (get-in result [:kotoba.cli/data :kotoba.wasm/result-type])))
    (is (= (.getPath output) (get-in result [:kotoba.cli/data :kotoba.wasm/output])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))
    (is (pos-int? (get-in result [:kotoba.cli/data :kotoba.wasm/byte-count])))))

(deftest wasm-emit-supports-callgraph-if-and-comparisons
  (let [run-result (launcher/dispatch ["run" "src/demo_call.kotoba" "--json"])
        forms (runtime/read-file "src/demo_call.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-call" ".wasm")
                 (.deleteOnExit))
        emit-result (launcher/dispatch ["wasm" "emit" "src/demo_call.kotoba" "--json"
                                        "--output" (.getPath output)])]
    (is (= 43 (get-in run-result [:kotoba.cli/data :kotoba.runtime/result
                                  :kotoba.runtime/value])))
    (is (:kotoba.wasm/ok? wasm))
    (is (= 3 (:kotoba.wasm/function-count wasm)))
    (is (:kotoba.cli/ok? emit-result))
    (is (= :wasm/binary-emitted (:kotoba.cli/code emit-result)))
    (is (= 3 (get-in emit-result [:kotoba.cli/data :kotoba.wasm/function-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-requires-policy-for-host-capability-import
  (let [forms (runtime/read-file "src/demo_cap.kotoba" :kotoba)
        denied (launcher/dispatch ["wasm" "emit" "src/demo_cap.kotoba" "--json"])
        policy (edn/read-string (slurp "src/demo_policy.edn"))
        allowed-wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-cap" ".wasm")
                 (.deleteOnExit))
        allowed (launcher/dispatch ["wasm" "emit" "src/demo_cap.kotoba"
                                    "--policy" "src/demo_policy.edn"
                                    "--json"
                                    "--output" (.getPath output)])]
    (is (false? (:kotoba.cli/ok? denied)))
    (is (= :wasm/check-failed (:kotoba.cli/code denied)))
    (is (= :capability-not-granted
           (get-in denied [:kotoba.cli/data :kotoba.runtime/result
                           :kotoba.runtime/problems 0 :kotoba.runtime/problem])))
    (is (:kotoba.wasm/ok? allowed-wasm))
    (is (= 1 (:kotoba.wasm/import-count allowed-wasm)))
    (is (= [{:module "kotoba"
             :field "has_capability"
             :params [:i32]
             :result :i32}]
           (:kotoba.wasm/imports allowed-wasm)))
    (is (:kotoba.cli/ok? allowed))
    (is (= :wasm/binary-emitted (:kotoba.cli/code allowed)))
    (is (= 1 (get-in allowed [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= 2 (get-in allowed [:kotoba.cli/data :kotoba.wasm/function-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-notify-provider-import
  (let [forms (runtime/read-file "src/demo_notify.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_policy.edn"))
        denied (launcher/dispatch ["wasm" "emit" "src/demo_notify.kotoba" "--json"])
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-notify" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_notify.kotoba"
                                    "--policy" "src/demo_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (false? (:kotoba.cli/ok? denied)))
    (is (= :capability-not-granted
           (get-in denied [:kotoba.cli/data :kotoba.runtime/result
                           :kotoba.runtime/problems 0 :kotoba.runtime/problem])))
    (is (:kotoba.wasm/ok? wasm))
    (is (= [{:module "kotoba"
             :field "notify_show"
             :capability "notify/show"
             :params [:i32]
             :result :i32}]
           (:kotoba.wasm/imports wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/function-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-core-provider-import-surface
  (let [forms (runtime/read-file "src/demo_providers.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_provider_policy.edn"))
        denied (launcher/dispatch ["wasm" "emit" "src/demo_providers.kotoba" "--json"])
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-providers" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_providers.kotoba"
                                    "--policy" "src/demo_provider_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (false? (:kotoba.cli/ok? denied)))
    (is (= :capability-not-granted
           (get-in denied [:kotoba.cli/data :kotoba.runtime/result
                           :kotoba.runtime/problems 0 :kotoba.runtime/problem])))
    (is (:kotoba.wasm/ok? wasm))
    (is (= 7 (:kotoba.wasm/import-count wasm)))
    (is (= ["clipboard_read"
            "clipboard_write"
            "http_fetch"
            "keychain_read"
            "keychain_write"
            "fs_read"
            "fs_write"]
           (mapv :field (:kotoba.wasm/imports wasm))))
    (is (= [[:i32 :i32]
            [:i32 :i32]
            [:i32 :i32 :i32 :i32]
            [:i32 :i32 :i32 :i32]
            [:i32 :i32 :i32 :i32]
            [:i32 :i32 :i32 :i32]
            [:i32 :i32 :i32 :i32]]
           (mapv :params (:kotoba.wasm/imports wasm))))
    (is (= 8 (:kotoba.wasm/data-segment-count wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 7 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= 8 (get-in emitted [:kotoba.cli/data :kotoba.wasm/data-segment-count])))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/function-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-literal-string-bytes-and-memory-export
  (let [run-result (launcher/dispatch ["run" "src/demo_memory.kotoba" "--json"])
        forms (runtime/read-file "src/demo_memory.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-memory" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_memory.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (= 106 (get-in run-result [:kotoba.cli/data :kotoba.runtime/result
                                   :kotoba.runtime/value])))
    (is (:kotoba.wasm/ok? wasm))
    (is (= true (:kotoba.wasm/memory? wasm)))
    (is (= 1 (:kotoba.wasm/memory-min-pages wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= true (get-in emitted [:kotoba.cli/data :kotoba.wasm/memory?])))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/memory-min-pages])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-mutable-memory-byte-writes
  (let [forms (runtime/read-file "src/demo_memory_write.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-memory-write" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_memory_write.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= 1 (:kotoba.wasm/data-segment-count wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/data-segment-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-bump-allocation
  (let [forms (runtime/read-file "src/demo_alloc.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-alloc" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_alloc.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (integer? (:kotoba.wasm/heap-base wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (integer? (get-in emitted [:kotoba.cli/data :kotoba.wasm/heap-base])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-checked-allocation
  (let [forms (runtime/read-file "src/demo_alloc_checked.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-alloc-checked" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_alloc_checked.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (integer? (:kotoba.wasm/heap-base wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-memory-grow
  (let [forms (runtime/read-file "src/demo_memory_grow.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-memory-grow" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_memory_grow.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= true (:kotoba.wasm/memory? wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-i64-main-result
  (let [forms (runtime/read-file "src/demo_i64.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-i64" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_i64.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i64 (:kotoba.wasm/result-type wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= :i64 (get-in emitted [:kotoba.cli/data :kotoba.wasm/result-type])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-i64-params-and-locals
  (let [forms (runtime/read-file "src/demo_i64_params.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-i64-params" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_i64_params.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i64 (:kotoba.wasm/result-type wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= :i64 (get-in emitted [:kotoba.cli/data :kotoba.wasm/result-type])))
    (is (= 2 (get-in emitted [:kotoba.cli/data :kotoba.wasm/function-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-i64-host-abi-signature
  (let [forms (runtime/read-file "src/demo_i64_host.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_i64_host_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-i64-host" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_i64_host.kotoba"
                                    "--policy" "src/demo_i64_host_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i64 (:kotoba.wasm/result-type wasm)))
    (is (= [{:module "kotoba"
             :field "host_i64_roundtrip"
             :capability "ledger/append"
             :params [:i64]
             :result :i64}]
           (:kotoba.wasm/imports wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= :i64 (get-in emitted [:kotoba.cli/data :kotoba.wasm/result-type])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-indirect-call-table
  (let [forms (runtime/read-file "src/demo_indirect.kotoba" :kotoba)
        wasm (runtime/wasm-binary forms)
        output (doto (java.io.File/createTempFile "kotoba-demo-indirect" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_indirect.kotoba"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= :i32 (:kotoba.wasm/result-type wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 3 (get-in emitted [:kotoba.cli/data :kotoba.wasm/function-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-string-pointer-length-provider-abi
  (let [forms (runtime/read-file "src/demo_string_abi.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_provider_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-string-abi" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_string_abi.kotoba"
                                    "--policy" "src/demo_provider_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= [{:module "kotoba"
             :field "clipboard_write_str"
             :capability "clipboard/text"
             :params [:i32 :i32]
             :result :i32}]
           (:kotoba.wasm/imports wasm)))
    (is (= 1 (:kotoba.wasm/data-segment-count wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/data-segment-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-provider-result-error-abi
  (let [forms (runtime/read-file "src/demo_provider_result.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_provider_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-provider-result" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_provider_result.kotoba"
                                    "--policy" "src/demo_provider_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= [{:module "kotoba"
             :field "http_fetch"
             :capability "http/fetch"
             :params [:i32 :i32 :i32 :i32]
             :result :i32}]
           (:kotoba.wasm/imports wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-structured-result-records
  (let [forms (runtime/read-file "src/demo_result_record.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_provider_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-result-record" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_result_record.kotoba"
                                    "--policy" "src/demo_provider_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= [{:module "kotoba"
             :field "http_fetch"
             :capability "http/fetch"
             :params [:i32 :i32 :i32 :i32]
             :result :i32}]
           (:kotoba.wasm/imports wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-supports-provider-buffer-writeback-abi
  (let [forms (runtime/read-file "src/demo_buffer_abi.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/demo_provider_policy.edn"))
        wasm (runtime/wasm-binary forms policy)
        output (doto (java.io.File/createTempFile "kotoba-demo-buffer-abi" ".wasm")
                 (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" "src/demo_buffer_abi.kotoba"
                                    "--policy" "src/demo_provider_policy.edn"
                                    "--output" (.getPath output)
                                    "--json"])]
    (is (:kotoba.wasm/ok? wasm))
    (is (= [{:module "kotoba"
             :field "clipboard_read"
             :capability "clipboard/text"
             :params [:i32 :i32]
             :result :i32}]
           (:kotoba.wasm/imports wasm)))
    (is (= 1 (:kotoba.wasm/data-segment-count wasm)))
    (is (:kotoba.cli/ok? emitted))
    (is (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/data-segment-count])))
    (is (= [0 97 115 109]
           (mapv #(bit-and % 0xff) (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(deftest wasm-emit-reports-policy-read-errors
  (let [result (launcher/dispatch ["wasm" "emit" "src/demo_notify.kotoba"
                                   "--policy" "missing-policy.edn"
                                   "--json"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :wasm/policy-not-readable (:kotoba.cli/code result)))
    (is (= "missing-policy.edn" (get-in result [:kotoba.cli/data :kotoba.policy/path])))))

(deftest wasm-run-actually-executes-a-trivial-module
  (let [result (launcher/dispatch ["wasm" "run" "src/demo.kotoba" "--json"])]
    (is (:kotoba.cli/ok? result))
    (is (= :wasm/run-completed (:kotoba.cli/code result)))
    (is (= 42 (get-in result [:kotoba.cli/data :kotoba.wasm/value])))
    (is (zero? (get-in result [:kotoba.cli/data :kotoba.wasm/import-count])))))

(deftest wasm-run-executes-kgraph-round-trip-end-to-end
  (let [result (launcher/dispatch ["wasm" "run" "src/demo_kgraph.kotoba"
                                   "--policy" "src/demo_kgraph_policy.edn"
                                   "--json"])]
    (is (:kotoba.cli/ok? result))
    (is (= :wasm/run-completed (:kotoba.cli/code result)))
    (is (pos? (get-in result [:kotoba.cli/data :kotoba.wasm/value]))
        "kgraph_query wrote a real (positive) byte count via the real Chicory host function")
    (is (= 2 (get-in result [:kotoba.cli/data :kotoba.wasm/import-count])))))

(deftest wasm-run-requires-policy-for-host-capability-import
  (let [result (launcher/dispatch ["wasm" "run" "src/demo_kgraph.kotoba" "--json"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :wasm/check-failed (:kotoba.cli/code result)))))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.launcher-test)]
    (when (pos? (+ (or fail 0) (or error 0)))
      (System/exit 1))))
