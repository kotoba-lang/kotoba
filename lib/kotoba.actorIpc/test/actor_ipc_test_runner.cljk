(ns actor-ipc-test-runner
  (:require [actor-ipc-test]
            [cljs.test :as test]))

(let [{:keys [fail error]} (test/run-tests 'actor-ipc-test)]
  (when (pos? (+ fail error))
    (js/process.exit 1)))
