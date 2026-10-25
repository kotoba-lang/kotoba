(ns r2-live-worker-guards
  "The benchmark worker's refusals, without a bucket.

  Three of the four ways this worker can decline never touch R2: the kill
  switch, the method check, and the bounds check. They are exactly the paths a
  live run would skip, so nothing else would ever exercise them -- and a worker
  whose kill switch silently stopped working would look identical to one that
  was never asked to run."
  (:require [r2-live-worker :as worker]
            [promesa.core :as p]))

(defn- post [body]
  (js/Request. "https://bench.invalid/"
               #js {:method "POST"
                    :headers #js {"content-type" "application/json"}
                    :body (js/JSON.stringify (clj->js body))}))

(def failures (atom 0))
(def checks (atom 0))

(defn- check! [name req env want]
  (-> (worker/fetch-handler req env)
      (p/then (fn [^js r]
                (swap! checks inc)
                (if (= want (.-status r))
                  (println "  ok" name (.-status r))
                  (do (swap! failures inc)
                      (println "FAIL" name "got" (.-status r) "want" want)))))))

(-> (p/do
      (check! "disabled -> 503" (post {}) #js {} 503)
      (check! "GET -> 405" (js/Request. "https://bench.invalid/") #js {:BENCH_LIVE_ENABLED "1"} 405)
      (check! "samples 1 -> 400" (post {:samples 1 :size 1024}) #js {:BENCH_LIVE_ENABLED "1"} 400)
      (check! "samples 101 -> 400" (post {:samples 101 :size 1024}) #js {:BENCH_LIVE_ENABLED "1"} 400)
      (check! "size 262145 -> 400" (post {:samples 10 :size 262145}) #js {:BENCH_LIVE_ENABLED "1"} 400)
      (check! "in bounds is NOT refused early" (post {:samples 10 :size 1024}) #js {} 503))
    (p/then (fn [_]
              ;; evidence floor: a run that checked nothing is not a pass
              (when (< @checks 6)
                (swap! failures inc)
                (println "FAIL: only" @checks "of 6 checks ran"))
              (if (zero? @failures)
                (println "r2 live bench worker guards:" @checks "checks passed")
                (do (println (str "r2 live bench worker guards: " @failures " failures"))
                    (set! (.-exitCode js/process) 1)))))
    (p/catch (fn [e] (js/console.error (str e)) (set! (.-exitCode js/process) 1))))
