(ns kotoba.captcha.server
  "Optional local host. `run-server` is injected (for example http-kit), keeping
  the library dependency-light and the lifecycle explicit."
  (:require [kotoba.lang.text :as str]
            [kotoba.captcha.http :as http]
            [kotoba.captcha.provider :as provider]
            [kotoba.captcha.store :as store]
            [kotoba.captcha.worker :as worker]
            [kotoba.captcha.worker-store :as worker-store]))

(defn start!
  [run-server config {:keys [port host] :or {port 8787 host "127.0.0.1"}}]
  (run-server (http/make-handler config) {:port port :ip host}))

(defn stop! [close-server]
  (when close-server (close-server)))

(defn start-worker!
  "Start a bounded background worker. Returns an idempotent stop function."
  [task-store providers {:keys [poll-ms worker-id options]
                         :or {poll-ms 100 worker-id "local-worker"}}]
  (let [running? (atom true)
        queue (worker-store/task-store-adapter task-store)
        operation (future
                    (while @running?
                      (when-not (worker/run-once!
                                 {:queue queue :providers providers
                                  :worker-id worker-id
                                  :clock #(System/currentTimeMillis)
                                  :options options})
                        (Thread/sleep (long poll-ms)))))
        stopped? (atom false)]
    (fn []
      (when (compare-and-set! stopped? false true)
        (reset! running? false)
        (future-cancel operation)))))

(defn -main [& _]
  (let [keys (some-> (System/getenv "KOTOBA_CAPTCHA_API_KEYS")
                     (str/split #",") seq)
        port (some-> (System/getenv "PORT") parse-long)
        run-server (requiring-resolve 'org.httpkit.server/run-server)]
    (when-not keys
      (throw (ex-info "KOTOBA_CAPTCHA_API_KEYS is required" {:type :missing-api-keys})))
    (let [task-store (store/memory-store)
          stop-worker (start-worker! task-store [(provider/synthetic-provider)] {})
          stop-server (start! run-server {:task-store task-store :api-keys keys}
                              {:port (or port 8787) :host "127.0.0.1"})]
      (.addShutdownHook (Runtime/getRuntime)
                        (Thread. #(do (stop-worker) (stop-server :timeout 100))))
      (println "kotoba-captcha listening on 127.0.0.1:" (or port 8787)))))
