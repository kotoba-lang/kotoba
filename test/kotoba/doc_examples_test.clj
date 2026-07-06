(ns kotoba.doc-examples-test
  "Regression gate for the `bin/kotoba-clj wasm emit`/`wasm run` command
  examples in docs/lang/README.md and docs/lang/gates.md. Those 39 examples
  went stale silently when F-001 made --package-lock mandatory (fixed in
  #286) -- every one of them would have failed with missing-lock-option if
  a reader had actually copy-pasted them. This test extracts every such
  example straight from the docs and runs it in-process through
  kotoba.launcher/dispatch, so a future change that breaks them (a new
  mandatory flag, a renamed option, ...) fails CI immediately instead of
  waiting for a human to notice the docs no longer work."
  (:require [clojure.java.io :as io]
            [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher]))

(def doc-files ["docs/lang/README.md" "docs/lang/gates.md"])

(defn- extract-commands
  "Every `bin/kotoba-clj wasm (emit|run) ... --json` line in TEXT, as argv
  vectors (kotoba.launcher/dispatch's own input shape) with the
  `bin/kotoba-clj` prefix stripped. Naive whitespace split -- fine, since
  none of these example commands quote an argument containing a space."
  [text]
  (->> (str/split-lines text)
       (keep (fn [line]
               (when (re-matches #"^bin/kotoba-clj wasm (emit|run) .*--json$" (str/trim line))
                 (-> (str/trim line)
                     (str/replace #"^bin/kotoba-clj " "")
                     (str/split #"\s+")
                     vec))))))

(deftest doc-wasm-emit-run-examples-still-work
  (doseq [doc-file doc-files
          :let [text (slurp (io/file doc-file))
                commands (extract-commands text)]]
    (testing (str doc-file " (" (count commands) " wasm emit/run examples)")
      (is (pos? (count commands)) (str doc-file " should have at least one wasm emit/run example"))
      (doseq [argv commands]
        (let [result (launcher/dispatch argv)]
          (is (true? (:kotoba.cli/ok? result))
              (str doc-file ": `bin/kotoba-clj " (str/join " " argv) "` failed: "
                   (pr-str (:kotoba.cli/code result)) " "
                   (pr-str (:kotoba.cli/data result)))))))))
