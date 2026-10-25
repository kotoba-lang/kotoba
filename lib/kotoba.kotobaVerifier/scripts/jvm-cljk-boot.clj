;; jvm-cljk-boot.clj -- JVM loader shim for .cljk sources (used by
;; scripts/jvm-cljk-run.sh; see that file's header).
;;
;; WHY: clojure.core/ns EVALUATES the ns attr-map on a real JVM, so the
;; `{:kotoba/export [some-symbol ...]}` lists these namespaces carry fail to
;; compile there -- "Unable to resolve symbol: assoc-some in this context",
;; measured 2026-10-19 on kotoba.lang.coll (pinned dep) and on this repo's
;; own kotoba.verifier.signing. The kbb/SCI engine treats the same attr-map
;; as data, which is why every suite routed through kbb is green while the
;; `:clj` reader branch (java.security Ed25519) has never compiled since the
;; .cljk rename. This bootstrap pre-interns those exported names as nil vars
;; so the ns form compiles UNMODIFIED; the namespace bodies then redefine the
;; real vars. The only value this changes is the :kotoba/export metadata
;; itself (it holds nils instead of symbols on the JVM) -- no code under test
;; is rewritten. The upstream fix is to quote the export vectors; this shim
;; exists so cross-host parity can be MEASURED at this pin.
;;
;; Usage (from jvm-cljk-run.sh): clojure.main jvm-cljk-boot.clj <overlay> <script> [args...]
;; Then loads <script> by path with *command-line-args* bound to [args...].
(require '[clojure.java.io :as io])
(import '[java.io PushbackReader])

(let [args (vec *command-line-args*)
      overlay (first args)
      target (second args)
      target-args (seq (drop 2 args))]
  ;; Pre-intern :kotoba/export names per namespace found in the overlay.
  (doseq [^java.io.File f (file-seq (io/file overlay))
          :when (and (.isFile f) (.endsWith (.getName f) ".cljc"))]
    (with-open [r (PushbackReader. (io/reader f))]
      (let [form (read {:read-cond :allow :features #{:clj}} r)]
        (when (and (seq? form) (= 'ns (first form)))
          (let [ns-sym (second form)
                attr (first (filter map? (drop 2 form)))
                exports (:kotoba/export attr)]
            (when (and ns-sym exports)
              (let [n (create-ns ns-sym)
                    syms (if (and (seq? exports) (= 'quote (first exports)))
                           (second exports)
                           exports)]
                (doseq [s syms
                        :when (symbol? s)]
                  (intern n (symbol (name s)) nil)))))))))
  (binding [*command-line-args* target-args]
    ;; Read/eval the target with :clj features rather than load-file: the
    ;; target keeps its .cljk name, and clojure's load-file would read a
    ;; non-.cljc extension WITHOUT reader conditionals ("Conditional read
    ;; not allowed", measured 2026-10-19).
    (with-open [r (PushbackReader. (io/reader target))]
      (loop []
        ;; (read opts stream) is the only arity with reader conditionals, and
        ;; it throws at EOF rather than returning a sentinel.
        (let [form (try (read {:read-cond :allow :features #{:clj}} r)
                        (catch RuntimeException e
                          (if (re-find #"EOF while reading" (str e))
                            ::eof
                            (throw e))))]
          (when-not (= ::eof form)
            (eval form)
            (recur)))))))
