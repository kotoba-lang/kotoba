(ns vultr.client-test
  (:require [clojure.test :refer [deftest is]]
            [vultr.client :as client]))

(defn- stub-http-fn [status body]
  (fn [_req] {:status status :body body}))

(deftest request-gets-with-bearer-auth-against-the-production-base-by-default
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"account\":{}}"})
        resp (client/request! "/account" {:http-fn http-fn :token "test-key"})]
    (is (= (str client/api-base "/account") (:url @captured)))
    (is (= :get (:method @captured)))
    (is (= "Bearer test-key" (get (:headers @captured) "Authorization")))
    (is (= {:account {}} resp))))

(deftest request-builds-a-query-string-from-the-query-opt
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{}"})]
    (client/request! "/instances" {:http-fn http-fn :token "t" :query {:label "web-1" :region "nrt"}})
    (is (re-find #"label=web-1" (:url @captured)))
    (is (re-find #"region=nrt" (:url @captured)))))

(deftest request-throws-on-non-2xx-transport-status
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"Vultr API request failed"
       (client/request! "/account" {:http-fn (stub-http-fn 401 "{\"error\":\"denied\"}") :token "t"}))))

(deftest request-returns-nil-for-an-empty-body-instead-of-a-parse-error
  (is (nil? (client/request! "/instances" {:http-fn (stub-http-fn 200 "") :token "t"}))))

(deftest api-key-fails-closed-without-env-or-explicit-token
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"VULTR_API_KEY is required"
       (client/request! "/account" {:http-fn (stub-http-fn 200 "{}")}))))
