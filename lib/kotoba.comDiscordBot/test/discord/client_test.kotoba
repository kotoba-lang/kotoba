(ns discord.client-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.lang.text :as str]
            [discord.client :as d]))

(defn- fake-io [responses]
  (let [calls (atom [])]
    {:calls calls
     :creds {:bot-token "tok-abc"}
     :json-write pr-str
     :json-read  (fn [s] (read-string s))
     :http-fn
     (fn [{:keys [url method] :as req}]
       (swap! calls conj req)
       (or (some (fn [[[m path-sub] resp]]
                   (when (and (= m method) (str/includes? url path-sub))
                     resp))
                 responses)
           {:status 404 :body "(nil)"}))}))

(deftest list-messages-sends-bot-auth-and-returns-vector
  (let [io (fake-io {[:get "/channels/C1/messages"]
                      {:status 200 :body (pr-str [{:id "1" :content "hi"}])}})
        out (d/list-messages io {:channel-id "C1"})]
    (is (= [{:id "1" :content "hi"}] out))
    (is (= "Bot tok-abc" (get-in (first @(:calls io)) [:headers "Authorization"])))))

(deftest list-messages-includes-after-param-when-given
  (let [io (fake-io {[:get "/channels/C1/messages"] {:status 200 :body (pr-str [])}})]
    (d/list-messages io {:channel-id "C1" :after "999"})
    (is (str/includes? (:url (first @(:calls io))) "after=999"))))

(deftest list-messages-returns-empty-on-failure
  (let [io (fake-io {[:get "/channels/C1/messages"] {:status 403 :body "(nil)"}})]
    (is (= [] (d/list-messages io {:channel-id "C1"})))))

(deftest send-message-posts-content
  (let [io (fake-io {[:post "/channels/C1/messages"]
                      {:status 200 :body (pr-str {:id "99" :content "hey"})}})
        out (d/send-message! io {:channel-id "C1" :text "hey"})]
    (is (= {:id "99" :content "hey"} out))
    (is (= {:content "hey"} (read-string (:body (first @(:calls io))))))))

(deftest send-message-returns-explicit-failure-shape-on-non-2xx
  (let [io (fake-io {[:post "/channels/C1/messages"] {:status 401 :body "unauthorized"}})
        out (d/send-message! io {:channel-id "C1" :text "hey"})]
    (is (false? (:ok out)))
    (is (= 401 (:status out)))))
