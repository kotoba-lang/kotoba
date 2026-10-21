# Compiled ClojureScript test bridge

`kotoba.test.cljs` exposes the host compiler's test macros and the same report
multimethod used by `cljs.test`. Select it explicitly for a ClojureScript
compiler build. The existing `kotoba.test` JVM/SCI function-shaped runner keeps
its existing API, namespace and protocol identities.

```clojure
(ns example.checks
  (:require [kotoba.test.cljs :as t])
  (:require-macros [kotoba.test.cljs :refer [deftest is async run-tests]]))

(deftest a-check (is (= 2 (+ 1 1))))

(defmethod t/report [:cljs.test/default :end-run-tests] [summary]
  (when-not (t/successful? summary)
    (set! (.-exitCode js/process) 1)))

(defn -main [] (run-tests 'example.checks))
(set! *main-cli-fn* -main)
```

Name every suite in `run-tests`. Requiring a test namespace alone does not run
it. Run the emitted Node bundle directly so asynchronous failure affects the
process the caller waits for. The compiler's REPL driver is a different
process and is not a reliable test exit gate.

```sh
node scripts/test-library-cljs.mjs /absolute/github/workspaces/compiled-tests
```

The gate compiles the actual bridge and fixture from byte-identical `.cljc`
views of their `.cljk` source, with a hash mapping in the evidence directory.
It verifies synchronous/async assertions, fixtures, shared report dispatch and
the exact discovered count. A second execution plants an async failure and an
exception in the same compiled artifact and must exit 1 with both counted.
Its pinned ClojureScript compiler uses the JVM for compilation. This is a
compiled ClojureScript compatibility gate; Amu native/Wasm qualification stays
separate.
