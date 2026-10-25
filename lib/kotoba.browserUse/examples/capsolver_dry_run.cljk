(ns capsolver-dry-run
  "Credential-free request-shape demonstration. No network request is made."
  (:require [browseruse.captcha :as captcha]
            [browseruse.capsolver :as capsolver]))

(defn -main [& _]
  (let [calls (atom [])
        responses (atom [{:status 200 :body {:errorId 0 :taskId "dry-task"}}
                         {:status 200 :body {:errorId 0 :status "ready"
                                            :solution {:token "dry-token"}}}])
        request! (fn [request]
                   (swap! calls conj (update request :body dissoc :clientKey))
                   (let [result (first @responses)]
                     (swap! responses subvec 1)
                     result))
        provider (capsolver/provider {:client-key "dry-run-only" :request! request!})
        result (captcha/solve!
                {:type :turnstile :url "https://example.test" :site-key "0x-public"}
                {:mode :external :provider provider :sleep-fn (fn [_])
                 :apply-solution (fn [_solution _challenge])})]
    (prn {:result (captcha/audit-result result) :requests @calls})))
