(ns kotoba.test-runner
  "Aggregate test entry point for `clojure -M:test`."
  (:require [clojure.test :refer [run-tests]]
            [kotoba.actor-host-test]
            [kotoba.aiueos-kernel-caps-test]
            [kotoba.cacao-run-test]
            [kotoba.cap-passing-test]
            [kotoba.cap-typed-test]
            [kotoba.did-adapter-test]
            [kotoba.doc-examples-test]
            [kotoba.git-adapter-test]
            [kotoba.host-providers-test]
            [kotoba.kgraph-test]
            [kotoba.launcher-test]
            [kotoba.package-admission-test]
            [kotoba.rad-adapter-test]
            [kotoba.real-host-providers-test]
            [kotoba.wasm-exec-test]))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.actor-host-test
                                        'kotoba.aiueos-kernel-caps-test
                                        'kotoba.cacao-run-test
                                        'kotoba.cap-passing-test
                                        'kotoba.cap-typed-test
                                        'kotoba.did-adapter-test
                                        'kotoba.doc-examples-test
                                        'kotoba.git-adapter-test
                                        'kotoba.host-providers-test
                                        'kotoba.kgraph-test
                                        'kotoba.launcher-test
                                        'kotoba.package-admission-test
                                        'kotoba.rad-adapter-test
                                        'kotoba.real-host-providers-test
                                        'kotoba.wasm-exec-test)]
    (when (pos? (+ (or fail 0) (or error 0)))
      (System/exit 1))))
