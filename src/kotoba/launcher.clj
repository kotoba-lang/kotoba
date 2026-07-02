(ns kotoba.launcher
  "Rust-free launcher for the CLJC Kotoba CLI authority.

  This is intentionally small: command semantics live in `kotoba.cli` from
  kotoba-lang/kotoba-lang. Host-specific launchers call into that namespace and
  render the returned data."
  (:require [cacao.core :as cacao-core]
            [clojure.data.json :as json]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.java.shell :as shell]
            [clojure.string :as str]
            [kotoba.cap-table :as cap-table]
            [kotoba.lang.capability-cacao :as capability-cacao]
            [kotoba.core.contracts :as core-contracts]
            [kotoba.cli :as cli]
            [kotoba.git-adapter :as git-adapter]
            [kotoba.host-providers :as host-providers]
            [kotoba.rad-adapter :as rad-adapter]
            [kotoba.package-admission :as package-admission]
            [kotoba.runtime :as runtime]
            [kotoba.selfhost.contracts :as selfhost]))

(defn result->exit [result]
  (if (:kotoba.cli/ok? result) 0 1))

(defn json-requested? [argv]
  (boolean (some #{"--json"} argv)))

(defn render-result
  ([result] (render-result result false))
  ([result json-output?]
   (if json-output?
     (json/write-str result :key-fn (fn [k]
                                      (if (keyword? k)
                                        (subs (str k) 1)
                                        (str k))))
     (pr-str result))))

(defn command-name [argv]
  (first argv))

(declare source-plan accepted-source? selfhost-result runtime-result wasm-result package-result contract-exports)

(def source-commands
  #{"run" "check"})

(def value-options
  #{"--cacao"
    "--kind"
    "--lock"
    "--manifest"
    "--output"
    "--package-lock"
    "--policy"
    "--reader-target"
    "--receipt"
    "--source-path"
    "--target"
    "--trust"
    "--host-command"
    "--host-arg"
    "--provider-command"
    "--text"
    "-S"
    "-o"})

(defn option-value [argv option]
  (some (fn [[current next]]
          (when (= current option) next))
        (partition-all 2 1 argv)))

(defn option-values [argv option]
  (keep (fn [[current next]]
          (when (= current option) next))
        (partition-all 2 1 argv)))

(defn reader-target-option [argv]
  (some-> (or (option-value argv "--reader-target")
              (option-value argv "--target"))
          keyword))

(defn reader-target-provided?
  "True when argv already carries a reader target option."
  [argv]
  (boolean (some #{"--reader-target" "--target"} argv)))

(defn source-positionals [argv]
  (loop [tokens (rest argv)
         positionals []]
    (if-let [token (first tokens)]
      (cond
        (value-options token)
        (recur (nnext tokens) positionals)

        (str/starts-with? token "-")
        (recur (next tokens) positionals)

        :else
        (recur (next tokens) (conj positionals token)))
      positionals)))

(defn first-source-arg [argv]
  (some #(when (accepted-source? %) %) (source-positionals argv)))

(defn source-argv-plan
  "Return the launcher source plan for run/check argv, if argv names a source."
  [argv]
  (when (source-commands (command-name argv))
    (when-let [source (first-source-arg argv)]
      (source-plan source (reader-target-option argv)))))

(defn normalize-source-argv
  "Reflect launcher source classification into argv sent to the CLJC authority."
  [argv]
  (let [argv (vec argv)
        plan (source-argv-plan argv)]
    (if (and plan
             (not (:kotoba.source/data? plan))
             (not (reader-target-provided? argv)))
      (conj argv "--reader-target" (name (:kotoba.source/reader-target plan)))
      argv)))

(defn authority-request
  "Formal request metadata for the delegated CLJC authority call."
  [original-argv normalized-argv plan]
  {:kotoba.launcher/authority "kotoba-lang/kotoba-lang"
   :kotoba.launcher/original-argv original-argv
   :kotoba.launcher/normalized-argv normalized-argv
   :kotoba.launcher/reader-target-added? (not= original-argv normalized-argv)
   :kotoba.launcher/source-plan plan})

(declare dispatch)

(defn shell-process-port
  "JVM process capability for host adapters (kotoba.git-adapter/IProcess)."
  []
  (reify git-adapter/IProcess
    (-run [_ argv]
      (apply shell/sh argv))))

(defn rad-host-port
  "JVM host capabilities for the rad adapter: filesystem writes plus
  in-process launcher re-dispatch (kotoba.rad-adapter/IRadHost)."
  []
  (reify rad-adapter/IRadHost
    (-mkdirs [_ path]
      (.mkdirs (io/file path)))
    (-write-file [_ path content]
      (let [f (io/file path)]
        (some-> (.getParentFile f) .mkdirs)
        (spit f content)))
    (-dispatch [_ argv]
      (dispatch argv))))

(defn adapter-result
  "Execute host-adapter-backed commands (:git, :rad) from their CLJC-planned
  result. Non-adapter commands pass through unchanged."
  [command result]
  (if (= :command/planned (:kotoba.cli/code result))
    (case command
      "git" (git-adapter/execute! (shell-process-port) result)
      "rad" (rad-adapter/execute! (rad-host-port) result)
      result)
    result))

(defn dispatch
  "Dispatch argv through the CLJC authority and return a result map."
  [argv]
  (let [argv (vec argv)]
    (if-let [launcher-result (case (command-name argv)
                               "selfhost" (selfhost-result argv)
                               "wasm" (wasm-result argv)
                               "package" (package-result argv)
                               nil)]
      launcher-result
      (let [contract (-> "lang/cli.edn"
                         io/resource
                         slurp
                         edn/read-string)
            normalized-argv (normalize-source-argv argv)
            result (cli/dispatch contract normalized-argv)
            plan (source-argv-plan normalized-argv)]
        (if-let [executed (and plan
                               (runtime-result (command-name normalized-argv)
                                               result
                                               argv
                                               normalized-argv
                                               plan))]
          executed
          (if plan
          (update result :kotoba.cli/data
                  (fnil assoc {})
                  :kotoba.launcher/source-plan plan
                  :kotoba.launcher/authority-request
                  (authority-request argv normalized-argv plan))
          (adapter-result (command-name argv) result)))))))

(defn resource-edn
  "Load an EDN resource by classpath path."
  [path]
  (let [resource (io/resource path)]
    (when-not resource
      (throw (ex-info "missing Kotoba resource" {:path path})))
    (-> resource slurp edn/read-string)))

(defn source-contract
  "Load the Kotoba source-kind contract. Dedicated .cljs source files are
  retired from profile v2; the :cljs reader target stays reachable via .cljc."
  []
  (core-contracts/source-contract))

(defn source-extension
  "Return the lowercase extension for a path-like string, including the dot."
  [path]
  (core-contracts/source-extension path))

(defn source-kind
  "Classify a source path under the source contract."
  ([path] (source-kind (source-contract) path))
  ([contract path]
   (core-contracts/source-kind contract path)))

(defn accepted-source?
  "True when a path has an accepted Kotoba source/data extension."
  [path]
  (core-contracts/accepted-source? (source-contract) path))

(defn source-plan
  "Return launcher-owned source dispatch data before delegating to CLJC authority."
  ([path] (source-plan path nil))
  ([path reader-target]
   (core-contracts/source-plan (source-contract) path reader-target)))

(def selfhost-seed-names
  selfhost/seed-names)

(defn selfhost-seed
  "Load a Kotoba selfhost EDN seed from launcher resources."
  [name]
  (selfhost/load-seed name))

(defn selfhost-seeds
  "Load every canonical Kotoba selfhost EDN seed bundled with the launcher."
  []
  (selfhost/load-seeds))

(defn seed-summary
  "Return stable public metadata for a selfhost seed."
  [[name seed]]
  (selfhost/seed-summary name seed))

(defn selfhost-list-result
  "List bundled Kotoba selfhost seeds."
  []
  (let [seeds (selfhost-seeds)]
    {:kotoba.cli/ok? true
     :kotoba.cli/code :selfhost/listed
     :kotoba.cli/data (selfhost/list-data seeds)}))

(defn selfhost-seed-problems
  "Return validation problems for a single selfhost seed."
  [[name seed]]
  (selfhost/seed-problems name seed))

(defn selfhost-check-result
  "Validate bundled Kotoba selfhost seeds without invoking any Rust crate."
  []
  (let [seeds (selfhost-seeds)
        data (selfhost/check-data seeds)
        ok? (empty? (:kotoba.selfhost/problems data))]
    {:kotoba.cli/ok? ok?
     :kotoba.cli/code (if ok? :selfhost/valid :selfhost/invalid)
     :kotoba.cli/data data}))

(defn selfhost-result
  "Handle launcher-owned selfhost commands."
  [argv]
  (case (second argv)
    "list" (selfhost-list-result)
    "check" (selfhost-check-result)
    {:kotoba.cli/ok? false
     :kotoba.cli/code :selfhost/unknown-command
     :kotoba.cli/data {:kotoba.selfhost/command (second argv)
                       :kotoba.selfhost/commands ["list" "check"]}}))

(defn admission-options
  "Package-admission option paths carried by argv. `lock-option` names the
  option holding the lock path (`--lock` for `package verify`,
  `--package-lock` for safe builds)."
  [argv lock-option]
  {:lock-path (option-value argv lock-option)
   :manifest-path (option-value argv "--manifest")
   :trust-path (option-value argv "--trust")
   :receipt-path (option-value argv "--receipt")})

(defn package-verify-result
  "Verify a package lock through the kotoba.lang.package-contract admission
  gate and emit the package-verification receipt."
  [argv]
  (package-admission/cli-result (admission-options argv "--lock")))

(defn package-result
  "Handle launcher-owned package admission commands."
  [argv]
  (case (second argv)
    "verify" (package-verify-result argv)
    {:kotoba.cli/ok? false
     :kotoba.cli/code :package/unknown-command
     :kotoba.cli/data {:kotoba.package/command (second argv)
                       :kotoba.package/commands ["verify"]
                       :kotoba.package/usage package-admission/usage}}))

(defn policy-result
  [argv]
  (if-let [path (option-value argv "--policy")]
    (try
      {:kotoba.policy/ok? true
       :kotoba.policy/path path
       :kotoba.policy/data (-> path io/file slurp edn/read-string)}
      (catch Exception e
        {:kotoba.policy/ok? false
         :kotoba.policy/path path
         :kotoba.policy/error (.getMessage e)}))
    {:kotoba.policy/ok? true
     :kotoba.policy/data nil}))

(defn cacao-chain-data
  "Chain vector from `--cacao` EDN: {:cacao/chain [\"b64\" ...]} or a plain
  EDN vector of base64 strings."
  [data]
  (cond
    (map? data) (:cacao/chain data)
    (vector? data) data
    :else nil))

(defn cacao-result
  "Load the `--cacao <file>` delegation chain, when the option is present."
  [argv]
  (if-let [path (option-value argv "--cacao")]
    (try
      {:kotoba.cacao/ok? true
       :kotoba.cacao/path path
       :kotoba.cacao/chain (cacao-chain-data
                            (-> path io/file slurp edn/read-string))}
      (catch Exception e
        {:kotoba.cacao/ok? false
         :kotoba.cacao/path path
         :kotoba.cacao/error (.getMessage e)}))
    {:kotoba.cacao/ok? true
     :kotoba.cacao/chain nil}))

(defn verified-cacao-chain
  "Real crypto boundary: verify the delegation chain (cacao.core/verify-chain,
  signatures + linkage + attenuation + expiry ordering + freshness at the
  current instant) and map the VERIFIED result to capability grants
  (kotoba.lang.capability-cacao/grants-from-chain — crypto-free).
  Returns {:chain <verify-chain result> :grants [..] :skipped [..]
           :problems <nil-or-problems>}."
  [chain]
  (let [verified (cacao-core/verify-chain chain
                                          {:now (str (java.time.Instant/now))})
        mapped (capability-cacao/grants-from-chain verified)]
    {:chain verified
     :grants (:grants mapped)
     :skipped (:skipped mapped)
     :problems (cond
                 ;; grants-from-chain fails closed on an unverified chain and
                 ;; already echoes the chain problems after :chain/not-verified
                 (seq (:problems mapped)) (vec (:problems mapped))
                 (not (:chain/valid? verified)) (vec (:chain/problems verified))
                 :else nil)}))

(defn contract-exports
  "Return common plus target-specific exports from a selfhost contract seed."
  ([seed] (contract-exports seed nil))
  ([seed target]
   (merge (:common-exports seed)
          (when target
            (get-in seed [:target-exports target])))))

(defn safe-analyzer-fact-classification
  "Return the Rust-free source fact classification seed."
  []
  (selfhost-seed "safe_analyzer_facts"))

(defn safe-analyzer-fact-classified?
  "True when `value` is listed under `classification` in safe_analyzer_facts.edn."
  [classification value]
  (boolean
   (some #{value}
         (get (safe-analyzer-fact-classification) classification))))

(defn source-file-readable?
  [plan]
  (let [file (io/file (:kotoba.source/path plan))]
    (and (.isFile file)
         (.canRead file))))

(defn runtime-data
  [original-argv normalized-argv plan runtime-result]
  {:kotoba.launcher/source-plan plan
   :kotoba.launcher/authority-request (authority-request original-argv normalized-argv plan)
   :kotoba.runtime/result runtime-result})

(defn guarded-run-result
  "Capability-guarded `run` (issue #263): the static check admits the policy's
  capabilities, and every host provider invocation is dispatched through
  kotoba.lang.capability-host/guard-call with grants/local policy derived from
  the policy EDN. The ordered receipt journal is attached to the result as
  :kotoba.host/receipts. HANDLERS optionally overrides the provider handler
  registry (kotoba.host-providers/default-handlers).

  The run also installs the S4b capability-passing surface: a per-run
  capability table (kotoba.cap-table) behind `cap-acquire` and the `<op>-with`
  use variants, sharing the same receipt journal and provider handlers.

  RUN-OPTS optionally carries :handlers (overriding
  kotoba.host-providers/default-handlers) and :cacao-grants (verified CACAO
  delegation-chain grants replacing the policy-derived grants; the local
  policy side still comes from POLICY, which therefore narrows the chain)."
  ([safe-facts plan forms policy] (guarded-run-result safe-facts plan forms policy nil))
  ([safe-facts plan forms policy {:keys [handlers cacao-grants]}]
   (let [{:keys [record! entries]} (host-providers/journal)
         now (str (java.time.LocalDate/now))
         opts (cond-> {:record! record! :now now}
                handlers (assoc :handlers handlers)
                cacao-grants (assoc :cacao-grants cacao-grants))
         host-call (host-providers/host-call policy opts)
         cap-table (cap-table/make-table)
         cap-fns (host-providers/capability-passing-fns cap-table policy opts)
         ran (runtime/run safe-facts plan forms
                          {:policy policy
                           :host-call host-call
                           :capability-query (host-providers/capability-query-fn policy)
                           :host-fns cap-fns})]
     (assoc ran :kotoba.host/receipts (entries)))))

(defn runtime-result
  "Run/check an existing source file through the CLJ-owned executable slice.

  When `--policy <path>` accompanies `run`/`check`, the policy EDN drives the
  static capability check, and `run` additionally installs the capability
  guard (see `guarded-run-result`). Without `--policy` the legacy ambient
  behavior is unchanged (host-import ops are rejected as
  :capability-not-granted and no receipts are emitted).

  When `--cacao <file>` accompanies `run`, the file's delegation chain is
  verified (cacao.core/verify-chain) and its grants replace the
  policy-derived grants for the guarded run; an invalid/expired chain aborts
  with :run/cacao-invalid before any execution. Without `--policy`, a policy
  admitting the chain's capability kinds is synthesized
  (kotoba.host-providers/grants->policy) so the local policy defaults to
  allowing whatever the chain grants — an explicit `--policy` narrows it."
  [command authority-result original-argv normalized-argv plan]
  (when (and (source-commands command)
             (source-file-readable? plan)
             (not (:kotoba.source/data? plan)))
    (let [policy-result (policy-result original-argv)
          policy (:kotoba.policy/data policy-result)]
      (if-not (:kotoba.policy/ok? policy-result)
        {:kotoba.cli/ok? false
         :kotoba.cli/code (if (= "run" command)
                            :run/policy-not-readable
                            :check/policy-not-readable)
         :kotoba.cli/data policy-result}
        (let [forms (runtime/read-file (:kotoba.source/path plan)
                                       (:kotoba.source/reader-target plan))
              safe-facts (safe-analyzer-fact-classification)]
          (case command
            "check"
            (let [checked (runtime/check safe-facts plan forms policy)
                  ok? (:kotoba.runtime/ok? checked)]
              {:kotoba.cli/ok? ok?
               :kotoba.cli/code (if ok? :check/valid :check/invalid)
               :kotoba.cli/data (merge (:kotoba.cli/data authority-result)
                                       (runtime-data original-argv normalized-argv plan checked))})

            "run"
            (let [cacao-load (cacao-result original-argv)]
              (cond
                (not (:kotoba.cacao/ok? cacao-load))
                {:kotoba.cli/ok? false
                 :kotoba.cli/code :run/cacao-not-readable
                 :kotoba.cli/data cacao-load}

                :else
                (let [cacao (when (:kotoba.cacao/path cacao-load)
                              (verified-cacao-chain
                               (:kotoba.cacao/chain cacao-load)))]
                  (if (:problems cacao)
                    ;; invalid/expired chain: the run does NOT proceed
                    {:kotoba.cli/ok? false
                     :kotoba.cli/code :run/cacao-invalid
                     :kotoba.cli/data {:kotoba.cacao/path (:kotoba.cacao/path cacao-load)
                                       :kotoba.cacao/problems (:problems cacao)}}
                    (let [effective-policy
                          (or policy
                              (when cacao
                                (host-providers/grants->policy (:grants cacao))))
                          ran (if effective-policy
                                (guarded-run-result safe-facts plan forms effective-policy
                                                    (when cacao
                                                      {:cacao-grants (:grants cacao)}))
                                (runtime/run safe-facts plan forms))
                          ok? (:kotoba.runtime/ok? ran)]
                      {:kotoba.cli/ok? ok?
                       :kotoba.cli/code (if ok? :run/completed :run/failed)
                       :kotoba.cli/data (merge (:kotoba.cli/data authority-result)
                                               (runtime-data original-argv normalized-argv plan
                                                             (dissoc ran :kotoba.host/receipts))
                                               (when effective-policy
                                                 {:kotoba.host/receipts (:kotoba.host/receipts ran)})
                                               (when policy
                                                 {:kotoba.policy/path (:kotoba.policy/path policy-result)})
                                               (when cacao
                                                 (let [chain (:chain cacao)]
                                                   {:kotoba.cacao/path (:kotoba.cacao/path cacao-load)
                                                    :kotoba.cacao/root-iss (:chain/root-iss chain)
                                                    :kotoba.cacao/holder (:chain/holder chain)
                                                    :kotoba.cacao/depth (:chain/depth chain)})))})))))

            nil))))))

(defn wasm-emit-result*
  [argv]
  (let [normalized-argv (normalize-source-argv (vec (cons "run" (rest argv))))
        plan (source-argv-plan normalized-argv)
        policy-result (policy-result argv)
        policy (:kotoba.policy/data policy-result)
        output (or (option-value argv "--output")
                   (option-value argv "-o"))]
    (cond
      (not (:kotoba.policy/ok? policy-result))
      {:kotoba.cli/ok? false
       :kotoba.cli/code :wasm/policy-not-readable
       :kotoba.cli/data policy-result}

      (nil? plan)
      {:kotoba.cli/ok? false
       :kotoba.cli/code :wasm/missing-source
       :kotoba.cli/data {:kotoba.wasm/usage "kotoba wasm emit <source> [--reader-target target]"}}

      (not (source-file-readable? plan))
      {:kotoba.cli/ok? false
       :kotoba.cli/code :wasm/source-not-readable
       :kotoba.cli/data {:kotoba.source/path (:kotoba.source/path plan)}}

      :else
      (let [forms (runtime/read-file (:kotoba.source/path plan)
                                     (:kotoba.source/reader-target plan))
            checked (runtime/check (safe-analyzer-fact-classification) plan forms policy)
            ir (:kotoba.runtime/ir checked)
            edn-bytes (when ir (runtime/wasm-artifact ir))
            wasm (when (:kotoba.runtime/ok? checked)
                   (runtime/wasm-binary forms policy))]
        (cond
          (not (:kotoba.runtime/ok? checked))
          {:kotoba.cli/ok? false
           :kotoba.cli/code :wasm/check-failed
           :kotoba.cli/data {:kotoba.launcher/source-plan plan
                             :kotoba.runtime/result checked
                             :kotoba.wasm/artifact-kind :kotoba.runtime/edn-ir
                             :kotoba.wasm/binary? false
                             :kotoba.wasm/byte-count (when edn-bytes (alength edn-bytes))}}

          (:kotoba.wasm/ok? wasm)
          (do
            (when output
              (let [file (io/file output)]
                (io/make-parents file)
                (with-open [out (io/output-stream file)]
                  (.write out ^bytes (:kotoba.wasm/binary wasm)))))
          {:kotoba.cli/ok? true
           :kotoba.cli/code :wasm/binary-emitted
           :kotoba.cli/data {:kotoba.launcher/source-plan plan
                             :kotoba.runtime/result checked
                             :kotoba.wasm/artifact-kind :webassembly/module
                             :kotoba.wasm/binary? true
                             :kotoba.wasm/byte-count (:kotoba.wasm/byte-count wasm)
                             :kotoba.wasm/export (:kotoba.wasm/export wasm)
                             :kotoba.wasm/result-type (:kotoba.wasm/result-type wasm)
                             :kotoba.wasm/function-count (:kotoba.wasm/function-count wasm)
                             :kotoba.wasm/local-count (:kotoba.wasm/local-count wasm)
                             :kotoba.wasm/import-count (:kotoba.wasm/import-count wasm)
                             :kotoba.wasm/imports (:kotoba.wasm/imports wasm)
                             :kotoba.wasm/memory? (:kotoba.wasm/memory? wasm)
                             :kotoba.wasm/memory-min-pages (:kotoba.wasm/memory-min-pages wasm)
                             :kotoba.wasm/heap-base (:kotoba.wasm/heap-base wasm)
                             :kotoba.wasm/data-segment-count (:kotoba.wasm/data-segment-count wasm)
                             :kotoba.wasm/output output
                             :kotoba.wasm/magic [0 97 115 109]}}
            )

          :else
          {:kotoba.cli/ok? false
           :kotoba.cli/code :wasm/binary-unsupported
           :kotoba.cli/data {:kotoba.launcher/source-plan plan
                             :kotoba.runtime/result checked
                             :kotoba.wasm/problems (:kotoba.wasm/problems wasm)
                             :kotoba.wasm/artifact-kind :kotoba.runtime/edn-ir
                             :kotoba.wasm/binary? false
                             :kotoba.wasm/byte-count (when edn-bytes (alength edn-bytes))}})))))

(defn wasm-emit-result
  "Safe-build entry point for `wasm emit`. When `--package-lock <path>` is
  provided, the package admission gate runs first and a rejected lock aborts
  the build with the package-verification receipt in the error payload. When
  no lock is provided there are no package inputs to admit and behavior is
  unchanged."
  [argv]
  (let [admission (when (option-value argv "--package-lock")
                    (package-admission/admit (admission-options argv "--package-lock")))]
    (if (and admission (not (:kotoba.admission/ok? admission)))
      {:kotoba.cli/ok? false
       :kotoba.cli/code :wasm/package-rejected
       :kotoba.cli/data (cond-> {:kotoba.package/admission-code (:kotoba.admission/code admission)}
                          (:kotoba.admission/receipt admission)
                          (assoc :kotoba.package/receipt (:kotoba.admission/receipt admission))

                          (:kotoba.admission/error admission)
                          (assoc :kotoba.package/error (:kotoba.admission/error admission)))}
      (cond-> (wasm-emit-result* argv)
        admission
        (update :kotoba.cli/data
                (fnil assoc {})
                :kotoba.package/receipt (:kotoba.admission/receipt admission))))))

(defn wasm-result
  "Handle launcher-owned Wasm-facing commands."
  [argv]
  (case (second argv)
    "emit" (wasm-emit-result argv)
    {:kotoba.cli/ok? false
     :kotoba.cli/code :wasm/unknown-command
     :kotoba.cli/data {:kotoba.wasm/command (second argv)
                       :kotoba.wasm/commands ["emit"]}}))

(defn -main [& argv]
  (let [result (dispatch argv)]
    (println (render-result result (json-requested? argv)))
    (System/exit (result->exit result))))
