(ns kotoba.launcher
  "Rust-free launcher for the CLJC Kotoba CLI authority.

  This is intentionally small: command semantics live in `kotoba.cli` from
  kotoba-lang/kotoba-lang. Host-specific launchers call into that namespace and
  render the returned data."
  (:require [clojure.data.json :as json]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [kotoba.core.contracts :as core-contracts]
            [kotoba.cli :as cli]
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

(declare source-plan accepted-source? selfhost-result runtime-result wasm-result contract-exports)

(def source-commands
  #{"run" "check"})

(def value-options
  #{"--kind"
    "--manifest"
    "--output"
    "--policy"
    "--reader-target"
    "--source-path"
    "--target"
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

(defn dispatch
  "Dispatch argv through the CLJC authority and return a result map."
  [argv]
  (let [argv (vec argv)]
    (if-let [launcher-result (case (command-name argv)
                               "selfhost" (selfhost-result argv)
                               "wasm" (wasm-result argv)
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
          result))))))

(defn resource-edn
  "Load an EDN resource by classpath path."
  [path]
  (let [resource (io/resource path)]
    (when-not resource
      (throw (ex-info "missing Kotoba resource" {:path path})))
    (-> resource slurp edn/read-string)))

(defn source-contract
  "Load the Kotoba source-kind contract."
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

(defn runtime-result
  "Run/check an existing source file through the CLJ-owned executable slice."
  [command authority-result original-argv normalized-argv plan]
  (when (and (source-commands command)
             (source-file-readable? plan)
             (not (:kotoba.source/data? plan)))
    (let [forms (runtime/read-file (:kotoba.source/path plan)
                                   (:kotoba.source/reader-target plan))
          safe-facts (safe-analyzer-fact-classification)]
      (case command
        "check"
        (let [checked (runtime/check safe-facts plan forms)
              ok? (:kotoba.runtime/ok? checked)]
          {:kotoba.cli/ok? ok?
           :kotoba.cli/code (if ok? :check/valid :check/invalid)
           :kotoba.cli/data (merge (:kotoba.cli/data authority-result)
                                   (runtime-data original-argv normalized-argv plan checked))})

        "run"
        (let [ran (runtime/run safe-facts plan forms)
              ok? (:kotoba.runtime/ok? ran)]
          {:kotoba.cli/ok? ok?
           :kotoba.cli/code (if ok? :run/completed :run/failed)
           :kotoba.cli/data (merge (:kotoba.cli/data authority-result)
                                   (runtime-data original-argv normalized-argv plan ran))})

        nil))))

(defn wasm-emit-result
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
