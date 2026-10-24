;; cljs CI runner: run the same deftests under nbb, exit nonzero on failure.
;;
;; Why this shape, and what the previous shape got wrong:
;;
;;   1. `cljs.test/set-env!` does NOT reach `run-all-tests`. The macro builds
;;      its own `(empty-env)` with :reporter :cljs.test/default, so report
;;      methods installed under a custom reporter key never dispatch. A
;;      failure counter fed by such methods stays at 0 forever, and the
;;      default reporter's own "FAIL in ..." output looks close enough to a
;;      custom one to hide it.
;;
;;   2. `run-all-tests` returns nil, not a summary and not a promise, so any
;;      exit decision written after the call is reading state from before the
;;      run completes. `(js/process.exit 0)` there also CLOBBERS the correct
;;      code nbb had already set.
;;
;; Both are fixed by the one hook cljs.test provides for exactly this:
;; :end-run-tests on the default reporter fires once the whole run block has
;; drained — synchronous tests and async ones alike — and receives the summary
;; map. We `set!` process.exitCode rather than calling process.exit so Node
;; still flushes stdout and finishes pending work before terminating.

(require '[cljs.test :as ct :refer-macros [run-all-tests]]
         '[kotoba.nio.bytebuffer-test])

;; Fail closed. If :end-run-tests never fires — a namespace blew up mid-load,
;; the run was truncated, the process drained early — the exit code stays
;; nonzero. A run that could not complete must not exit like a run that
;; completed and passed.
(set! (.-exitCode js/process) 1)

(defmethod ct/report [:cljs.test/default :end-run-tests] [m]
  (let [{:keys [test pass fail error]} m]
    (println (str "\nnbb-ci: " test " tests, " (+ pass fail error) " assertions, "
                  fail " failures, " error " errors."))
    (cond
      ;; Evidence floor: zero assertions means the suite did not run, which is
      ;; not the same answer as "the suite ran and found nothing wrong".
      (zero? (+ pass fail error))
      (do (println "nbb-ci: REFUSING to report a pass — no assertions ran.")
          (set! (.-exitCode js/process) 2))

      (ct/successful? m)
      (set! (.-exitCode js/process) 0)

      :else
      (set! (.-exitCode js/process) 1))))

(run-all-tests)
