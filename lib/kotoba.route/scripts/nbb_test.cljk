(ns nbb-test
  "Run the suite on ClojureScript. `route.core` is `.cljc` and the apps that use
  it are browser apps, so a JVM-only suite would return green for a namespace
  that does not load where it is actually used."
  (:require [cljs.test] [route.core-test]))

(def ^:private min-tests 5)

(defmethod cljs.test/report [:cljs.test/default :end-run-tests] [m]
  (let [{:keys [test pass fail error]} m]
    (println (str "\nRan " test " tests containing " (+ pass fail error) " assertions."))
    (println (str fail " failures, " error " errors."))
    (cond
      (< test min-tests) (do (println (str "REFUSING to report a pass: ran " test
                                           " tests, floor is " min-tests))
                             (js/process.exit 2))
      (or (pos? fail) (pos? error)) (js/process.exit 1)
      :else (js/process.exit 0))))

(cljs.test/run-tests 'route.core-test)
