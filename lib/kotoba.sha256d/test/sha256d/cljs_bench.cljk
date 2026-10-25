(ns sha256d.cljs-bench
  "Run the evolve tournament under ClojureScript/node -- the first time the *performance*
  side of the harness (not just correctness) runs off the JVM. Answers round 7's standing
  question: do the JVM speed conclusions (rolling worst, transient ~tie, Ch/Maj noise) hold
  on V8, where there is no boxed-`Long` problem and the GC/JIT differ? The cljs gene pool
  excludes the JVM-only `:mutable`/`:primitive` schedules, so this ranks the 27 portable
  candidates (:ch 3 x :maj 3 x :schedule {precompute, rolling, precompute-transient})."
  (:require [sha256d.core :as core]
            [sha256d.evolve :as evolve]))

(defn -main [& _]
  ;; round 10 head-to-head: does inlining ch/maj into the V8 fast path help (as it did ~13%
  ;; on the JVM)? Alternating, high-iter medians so a small delta is visible.
  (let [payload evolve/default-payload
        opts {:iters 4000 :reps 15}
        v8   #(core/sha256-bytes-with core/compress-v8 % core/ch core/maj)
        v8i  #(core/sha256-bytes-with core/compress-v8-inline % core/ch core/maj)]
    (dotimes [_ 3] (evolve/bench-ns-per-hash v8 payload opts) (evolve/bench-ns-per-hash v8i payload opts))
    (println "# V8 head-to-head: compress-v8 vs compress-v8-inline\n")
    (dotimes [i 4]
      (let [a (evolve/bench-ns-per-hash v8 payload opts)
            b (evolve/bench-ns-per-hash v8i payload opts)]
        (println (str "run " i "  v8=" (js/Math.round a) "  v8-inline=" (js/Math.round b)
                      "  inline/v8=" (.toFixed (/ b a) 3))))))
  ;; same default methodology as the JVM run (200 iters x 7 reps, 3 generations) so the
  ;; rankings are comparable; `now-ns`'s cljs branch uses js/performance.now (ns via *1e6).
  (println "\n# ClojureScript / node tournament (V8)\n")
  (println (evolve/report->markdown (evolve/run-tournament {}))))

(set! *main-cli-fn* -main)
