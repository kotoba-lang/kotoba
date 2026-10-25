(ns vultr.instances-test
  (:require [clojure.test :refer [deftest is]]
            [vultr.instances :as instances]))

(deftest list-instances-hits-the-instances-path-with-no-query-by-default
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"instances\":[]}"})]
    (is (= [] (instances/list-instances {:http-fn http-fn :token "t"})))
    (is (re-find #"/instances$" (:url @captured)))))

(deftest list-instances-passes-narrowing-filters-through
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"instances\":[]}"})]
    (instances/list-instances {:http-fn http-fn :token "t" :label "web-1" :tag "prod" :region "nrt"})
    (is (re-find #"label=web-1" (:url @captured)))
    (is (re-find #"tag=prod" (:url @captured)))
    (is (re-find #"region=nrt" (:url @captured)))))

(deftest get-instance-hits-the-instance-by-id-and-unwraps-the-envelope
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req)
                  {:status 200 :body "{\"instance\":{\"id\":\"abc\",\"status\":\"active\"}}"})]
    (is (= {:id "abc" :status "active"} (instances/get-instance "abc" {:http-fn http-fn :token "t"})))
    (is (re-find #"/instances/abc$" (:url @captured)))))
