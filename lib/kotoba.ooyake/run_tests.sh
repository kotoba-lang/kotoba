#!/usr/bin/env bash
# ooyake — clj/bb test suite (ADR-2606021600 cells py→clj port wave).
# Runs all cljc test namespaces via babashka from the repo root.
# Covers the two gated cell state machines: reconcile + world_model.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec kbb -e '(def nss (quote [ooyake.cells.reconcile.test-state-machine
                             ooyake.cells.world-model.test-state-machine]))
              (apply require (quote clojure.test) nss)
              (let [r (apply clojure.test/run-tests nss)]
                (System/exit (if (zero? (+ (:fail r) (:error r))) 0 1)))'
