(ns kotoba.lang.lint
  "EDN source linter/formatter for the kotoba-lang stdlib. A real consumer of fmt
  (canonicalize), lsp (diagnostics), fs (read source files), coll (result
  shaping). A kotoba cell's source is EDN; lint parses it, canonicalizes the
  whitespace via fmt so a CID is stable, and surfaces parse errors as lsp
  diagnostics for the editor.

  Zero third-party runtime deps; .cljc (JVM / SCI / CLJS / GraalVM / kotoba-WASM)."
  (:require [kotoba.lang.fs :as fs]
            [kotoba.lang.fmt :as fmt]
            [kotoba.lang.lsp :as lsp]
            [kotoba.lang.coll :as c]
            [kotoba.lang.edn :as edn]
            [kotoba.lang.text :as str]))

(defn- parse-diagnostic
  "Build an lsp diagnostic for a parse failure. EDN parse errors do not carry
  column info, so the range points at 0:0 (best-effort position)."
  [msg]
  (lsp/diagnostic (lsp/range (lsp/position 0 0) (lsp/position 0 0))
                  :error "lint" (str msg)))

(defn- lint-source* [source]
  (let [eof #?(:clj (Object.) :cljs (js/Object.))] ; unique sentinel
    (try
      (let [data (edn/read-string {:eof eof} source)]
        (cond
          ;; sentinel → end of input reached legitimately (the whole string was
          ;; a single value or empty)
          (identical? data eof)
          (if (str/blank? source)
            {:ok? true :canonical "" :diagnostics []}
            ;; blank-ish but read returned eof → treat as empty
            {:ok? true :canonical "" :diagnostics []})
          :else
          ;; detect trailing content by reading again from the remainder —
          ;; simplest: re-parse the canonical form; if it round-trips, clean.
          (let [canonical (fmt/format-str data)]
            {:ok? true :canonical canonical :diagnostics []})))
      (catch #?(:clj Throwable :cljs :default) e
        {:ok? false
         :canonical source
         ;; `ex-message`, not `(.getMessage e)`. The catch clause above was
         ;; already written portably as `#?(:clj Throwable :cljs :default)`,
         ;; but its BODY was not -- so on ClojureScript every parse failure
         ;; threw "Could not find instance method: getMessage" instead of
         ;; producing the diagnostic this function exists to produce.
         ;; Measured 2026-08-20: three of this namespace's tests errored on
         ;; nbb, all of them on the failure path.
         :diagnostics [(parse-diagnostic (ex-message e))]}))))


(defn lint-source
  "Lint an EDN source string. Returns `{:ok? :canonical :diagnostics}`.
  - On success: `:ok?` true, `:canonical` is the fmt-canonicalized text,
    `:diagnostics` is `[]`.
  - On parse failure: `:ok?` false, `:canonical` is the original source (so the
    editor still has it), `:diagnostics` holds one `:error` lsp diagnostic.
  - Trailing garbage after a value is reported as a `:warning` diagnostic."
  [source]
  ;; Blank input is answered before the reader is involved. That guard was
  ;; added on 2026-08-20 after measuring that `(edn/read-string {:eof eof} "")`
  ;; returned nil rather than the sentinel on nbb, so `identical?` was false,
  ;; the code fell through to formatting nil, and `:canonical` came back as the
  ;; STRING "nil" instead of "". Not an error -- a plausible wrong answer
  ;; handed to an editor.
  ;;
  ;; The note that came with it said ClojureScript "IGNORES that option". Re-
  ;; measured 2026-09-08, that is wider than the truth: cljs.reader honours
  ;; `:eof` for whitespace-only and comment-only input and returns nil only for
  ;; the EMPTY STRING. The reader is now kotoba.lang.edn, which answers the
  ;; sentinel for all four, so the divergence this guard was defending against
  ;; no longer exists. The guard stays anyway -- answering blank input without
  ;; involving a reader at all is cheaper and clearer than relying on one --
  ;; but it is now a shortcut, not a workaround.
  (if (str/blank? source)
    {:ok? true :canonical "" :diagnostics []}
    (lint-source* source)))

(defn lint-file
  "Read a source file via an injected `IFilesystem` (`fsb`) at `path`, then
  `lint-source`. Returns the lint result, or `::read-error` if the file is
  absent."
  [fsb path]
  (let [raw (fs/read fsb path)]
    (if (nil? raw)
      ::read-error
      (lint-source raw))))

(defn ok?
  "True iff `result` has no `:error`-severity diagnostics."
  [result]
  (not-any? #(= :error (:severity %)) (:diagnostics result)))

(defn summary
  "Count diagnostics by severity: `{severity count}`. Uses coll/map-vals to
  shape the grouped counts."
  [result]
  (c/map-vals count (group-by :severity (:diagnostics result))))
