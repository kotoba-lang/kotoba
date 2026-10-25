#!/usr/bin/env bash
# kotoba-actors-clj — clj/bb test suite (parallel Clojure/kotoba-datomic refactor project).
# Self-contained: runs from the actor dir with its own src:test classpath; joins the green-check.
set -euo pipefail
cd "$(dirname "$0")"
exec kbb --classpath src:test -e '(require (quote clojure.test) (quote kotoba-actors.kabuto-test))(let [r (clojure.test/run-tests (quote kotoba-actors.kabuto-test))](System/exit (if (zero? (+ (:fail r) (:error r))) 0 1)))'
