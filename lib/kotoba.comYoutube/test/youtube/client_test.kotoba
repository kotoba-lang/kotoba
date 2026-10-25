(ns youtube.client-test
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [youtube.client :as client]))

(deftest refresh-access-token-test
  (testing "success"
    (let [calls (atom [])
          stub (fn [req] (swap! calls conj req)
                 {:status 200 :body "{\"access_token\":\"tok123\"}" :response-headers {}})
          tok (client/refresh-access-token!
               {:client-id "cid" :client-secret "sec" :refresh-token "rt"}
               {:http-fn stub})]
      (is (= "tok123" tok))
      (is (= :post (:method (first @calls))))
      (is (str/includes? (:body (first @calls)) "grant_type=refresh_token"))))
  (testing "http failure"
    (let [stub (fn [_] {:status 401 :body "bad" :response-headers {}})]
      (is (thrown? clojure.lang.ExceptionInfo
                   (client/refresh-access-token! {:client-id "c" :client-secret "s" :refresh-token "r"}
                                                 {:http-fn stub})))))
  (testing "missing access_token in response"
    (let [stub (fn [_] {:status 200 :body "{}" :response-headers {}})]
      (is (thrown? clojure.lang.ExceptionInfo
                   (client/refresh-access-token! {:client-id "c" :client-secret "s" :refresh-token "r"}
                                                 {:http-fn stub}))))))

(deftest auth-header-test
  (is (= {"Authorization" "Bearer abc"} (client/auth-header "abc"))))
