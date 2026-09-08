(ns run-tests
  "The portable slice of kotoba/kotoba on nbb -- no JVM in this path.

  `scripts/verify-portable-source-tested-on-one-host.cljs` (the
  com-junkawasaki superproject) named 8 `.cljc` source namespaces in this
  repo reached only by `.clj` tests: demo, kotoba.deploy-adapter,
  kotoba.did-adapter, kotoba.git-adapter, kotoba.kagi-boundary,
  kotoba.kami-host, kotoba.rad-adapter, kotoba.sensing-host. `demo` was a
  detector false-positive -- no test anywhere actually requires that
  namespace, `demo` in the flagged `.clj` files is a local `{:keys [demo]}`
  destructuring bind that happens to share the word. The other 7 are real:
  each had a genuinely portable subset of its `.clj` test moved here
  (either the whole file, when every deftest was pure, or a new
  `*-portable-test.cljc` sibling holding the deftests that touch no host
  I/O, with the JVM-only remainder -- Chicory, `java.nio.file`, a real `git`
  subprocess, `kotoba.launcher`/`kotoba.runtime` end-to-end -- left in the
  original `.clj` file). See each ported/split file's own docstring for
  exactly what stayed JVM-only and why.

  kotoba.deploy-adapter is a partial exception worth restating here: its
  pure `plan`/`parse-target`/`public-urls`/`validate-control-plane-profile`
  surface is covered below, but `execute!` itself was NOT ported, because
  its private `read-edn` has a `:cljs` branch that is a bare `nil` (no
  `clojure.edn` require on that branch at all) -- verified separately that
  nbb DOES support `clojure.edn/read-string` directly, so this is a real,
  currently-unaddressed host behaviour gap in this .cljc namespace, not a
  reason to avoid porting the parts that do not depend on it.

  Run from the repo root:
    CP=$(clojure -Spath -M:test)
    nbb --classpath \"src:test:$CP\" run-tests.cljs"
  (:require [cljs.test :as t]
            [kotoba.did-adapter-test]
            [kotoba.git-adapter-portable-test]
            [kotoba.kagi-boundary-portable-test]
            [kotoba.kami-host-portable-test]
            [kotoba.rad-adapter-portable-test]
            [kotoba.sensing-host-portable-test]
            [kotoba.deploy-adapter-portable-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\nnbb: " (:test m) " tests, " (:pass m) " passed, "
                (:fail m) " failed, " (:error m) " errors"))
  (when (pos? (+ (or (:fail m) 0) (or (:error m) 0)))
    (set! (.-exitCode js/process) 1)))

(t/run-tests 'kotoba.did-adapter-test
             'kotoba.git-adapter-portable-test
             'kotoba.kagi-boundary-portable-test
             'kotoba.kami-host-portable-test
             'kotoba.rad-adapter-portable-test
             'kotoba.sensing-host-portable-test
             'kotoba.deploy-adapter-portable-test)
