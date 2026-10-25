(ns viber.client-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.lang.text :as str]
            [viber.client :as v]))

(defn- fake-io [status body]
  (let [calls (atom [])]
    {:calls calls
     :creds {:bot-token "tok-abc"}
     :json-write pr-str
     :json-read  (fn [s] (read-string s))
     :http-fn    (fn [req] (swap! calls conj req) {:status status :body body})}))

(deftest send-message-sends-auth-token-header-and-receiver-payload
  (let [io (fake-io 200 (pr-str {:status 0 :status_message "ok" :message_token 123}))
        out (v/send-message! io {:receiver "U1" :text "hi"})]
    (is (= {:status 0 :status_message "ok" :message_token 123} out))
    (let [{:keys [url headers body]} (first @(:calls io))]
      (is (str/includes? url "/send_message"))
      (is (= "tok-abc" (get headers "X-Viber-Auth-Token")))
      (is (= {:receiver "U1" :type "text" :sender {:name "manimani"} :text "hi"}
             (read-string body))))))

(deftest send-message-returns-explicit-failure-shape-on-non-200
  (let [io (fake-io 401 "unauthorized")
        out (v/send-message! io {:receiver "U1" :text "hi"})]
    (is (false? (:ok out)))
    (is (= 401 (:status out)))))

(deftest set-webhook-defaults-event-types-to-message-only
  (let [io (fake-io 200 (pr-str {:status 0 :event_types ["message"]}))]
    (v/set-webhook! io {:url "https://example.com/webhook/viber"})
    (is (= {:url "https://example.com/webhook/viber" :event_types ["message"]}
           (read-string (:body (first @(:calls io))))))))
