(ns r2-live-bench-driver
  "The bench driver's own failure discrimination, without a live bucket.

  `check!` must answer differently for three states that a naive driver would
  collapse into one: the race never ran, the race ran and more than one writer
  won, and the race ran and exactly one writer won. A driver that treats a
  missing `conditional_race` block as a pass would report success for a worker
  that never performed the race at all -- the shape ADR-2608136000 names."
  (:require [r2-live-bench :as bench]))

(defn- caught [f]
  (try (f) nil (catch :default e (str e))))

(def missing (caught #(bench/check! (js/JSON.parse "{\"p50_ms\":1}"))))
(def two     (caught #(bench/check! (js/JSON.parse "{\"conditional_race\":{\"winners\":2}}"))))
(def zero    (caught #(bench/check! (js/JSON.parse "{\"conditional_race\":{\"winners\":0}}"))))
(def one     (caught #(bench/check! (js/JSON.parse "{\"conditional_race\":{\"winners\":1}}"))))

(def failures (atom 0))
(defn- is! [ok? msg]
  (when-not ok? (swap! failures inc) (println "FAIL:" msg)))

(is! (some? missing) "a response with no conditional_race block must not pass")
(is! (re-find #"did not run" (or missing "")) "the missing-block message must say the race did not run")
(is! (some? two) "two winners must not pass")
(is! (re-find #"2 winners" (or two "")) "the wrong-count message must name the count")
(is! (some? zero) "zero winners must not pass")
(is! (nil? one) "exactly one winner must pass")
(is! (not= missing two) "the two failures must not produce the same message")

(if (zero? @failures)
  (println "r2 live bench driver: 7 checks passed")
  (do (println (str "r2 live bench driver: " @failures " failures"))
      (set! (.-exitCode js/process) 1)))
