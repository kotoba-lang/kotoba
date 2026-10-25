#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec kbb -e '
(require (quote clojure.test)
         (quote etzhayyim.ie-flow.test-boundary)
         (quote etzhayyim.ie-flow.test-colony)
         (quote etzhayyim.ie-flow.test-control)
         (quote etzhayyim.ie-flow.test-coscientist)
         (quote etzhayyim.ie-flow.test-dynamics)
         (quote etzhayyim.ie-flow.test-embed)
         (quote etzhayyim.ie-flow.test-gate-adapter)
         (quote etzhayyim.ie-flow.test-ledger)
         (quote etzhayyim.ie-flow.test-lifecycle)
         (quote etzhayyim.ie-flow.test-metrics)
         (quote etzhayyim.ie-flow.test-metrics-properties)
         (quote etzhayyim.ie-flow.test-react)
         (quote etzhayyim.ie-flow.test-reward)
         (quote etzhayyim.ie-flow.test-score))
(let [namespaces [                  (quote etzhayyim.ie-flow.test-boundary)
                  (quote etzhayyim.ie-flow.test-colony)
                  (quote etzhayyim.ie-flow.test-control)
                  (quote etzhayyim.ie-flow.test-coscientist)
                  (quote etzhayyim.ie-flow.test-dynamics)
                  (quote etzhayyim.ie-flow.test-embed)
                  (quote etzhayyim.ie-flow.test-gate-adapter)
                  (quote etzhayyim.ie-flow.test-ledger)
                  (quote etzhayyim.ie-flow.test-lifecycle)
                  (quote etzhayyim.ie-flow.test-metrics)
                  (quote etzhayyim.ie-flow.test-metrics-properties)
                  (quote etzhayyim.ie-flow.test-react)
                  (quote etzhayyim.ie-flow.test-reward)
                  (quote etzhayyim.ie-flow.test-score)]
      result (apply clojure.test/run-tests namespaces)]
  (System/exit (if (zero? (+ (:fail result) (:error result))) 0 1)))'
