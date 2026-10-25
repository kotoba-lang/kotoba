(ns kotoba.prng-cljs-verify
  "ClojureScript/node portability proof: compile the same .cljc source to JS
  and assert the PRNG answers IDENTICALLY to the JVM for the same seed. The
  expected literals are the JVM-measured draws for seed 42 (see prng-test);
  a divergence here means the hosts drifted."
  (:require [kotoba.prng :as prng]))

(def ^:private jvm-w42 3326932332)   ; (word-32 (seed-state 42)) — JVM measured
(def ^:private jvm-i42 108)          ; (next-int (seed-state 42) 256) — JVM measured

(defn- check!
  [label ok?]
  (println (if ok? (str "PASS " label) (str "FAIL " label)))
  (when-not ok? (js/process.exit 1)))

(defn -main [& _]
  (let [s0 (prng/seed-state 42)
        [w _]   (prng/word-32 s0)
        [v _]   (prng/next-int s0 256)
        [w1 _]  (prng/word-32 s0)
        w1' (-> (prng/word-32 s0) first)]
    (check! "word-32 host-parity (JVM 3326932332)" (= w jvm-w42))
    (check! "next-int host-parity (JVM 108)"      (= v jvm-i42))
    (check! "word-32 deterministic on node" (= w1 w1'))
    (check! "word-32 in range" (and (>= w 0) (< w 0x100000000)))
    (println "cljs verify OK")))

(set! *main-cli-fn* -main)