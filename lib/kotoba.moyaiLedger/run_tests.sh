#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec kbb -e '(require (quote clojure.test) (quote moyai.ledger-test)) (let [r (clojure.test/run-tests (quote moyai.ledger-test))] (System/exit (if (zero? (+ (:fail r) (:error r))) 0 1)))'
