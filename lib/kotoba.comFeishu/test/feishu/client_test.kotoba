(ns feishu.client-test
  (:require [clojure.test :refer [deftest testing is]]
            [feishu.client :as client]))

(defn- io [resp]
  {:http-fn (fn [_req] resp)
   :json-write pr-str
   :json-read identity
   :creds {:app-id "app-1" :app-secret "secret-1"}})

(deftest fetch-tenant-access-token!-success-test
  (is (= {:tenant-access-token "t-abc" :expire 7200}
         (client/fetch-tenant-access-token!
          (io {:status 200 :body {:code 0 :msg "ok" :tenant_access_token "t-abc" :expire 7200}})))))

(deftest fetch-tenant-access-token!-code-nonzero-is-failure-test
  (testing "HTTP 200 but Feishu-level code != 0 must NOT be reported as success"
    (is (= {:ok false :status :error :error "invalid app_secret"}
           (client/fetch-tenant-access-token!
            (io {:status 200 :body {:code 10003 :msg "invalid app_secret"}}))))))

(deftest fetch-tenant-access-token!-http-failure-test
  (is (= {:ok false :status 500 :error "boom"}
         (client/fetch-tenant-access-token! (io {:status 500 :body "boom"})))))

(deftest send-message!-test
  (testing "200 returns parsed body"
    (is (= {:ok true}
           (client/send-message!
            {:http-fn (fn [_req] {:status 200 :body {:ok true}})
             :json-write pr-str :json-read identity}
            {:receive-id "ou_abc" :text "hi" :tenant-access-token "t-abc"}))))
  (testing "non-200 returns the universal failure shape"
    (is (= {:ok false :status 403 :error "forbidden"}
           (client/send-message!
            {:http-fn (fn [_req] {:status 403 :body "forbidden"})
             :json-write pr-str :json-read identity}
            {:receive-id "ou_abc" :text "hi" :tenant-access-token "t-abc"})))))

(deftest send-message!-request-shape-test
  (testing "double-encodes content as its own JSON string, carries Bearer token"
    (let [captured (atom nil)
          io {:http-fn (fn [req] (reset! captured req) {:status 200 :body {:ok true}})
              :json-write pr-str :json-read identity}]
      (client/send-message! io {:receive-id "ou_abc" :text "hi" :tenant-access-token "t-abc"})
      (is (re-find #"receive_id_type=open_id" (:url @captured)))
      (is (= "Bearer t-abc" (get-in @captured [:headers "Authorization"])))
      (is (re-find #"content" (:body @captured)))
      (is (re-find #"hi" (:body @captured)))
      (is (re-find #"ou_abc" (:body @captured))))))
