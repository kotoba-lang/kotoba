(ns facebook-graph.client-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.lang.text :as str]
            [facebook-graph.client :as client]))

(defn- stub-http-fn [status body]
  (fn [_req] {:status status :body body}))

(deftest call-uses-bearer-auth-and-versioned-base
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"data\":[]}"})]
    (client/call! "/act_123/campaigns" {:http-fn http-fn :token "test-token"})
    (is (= "https://graph.facebook.com/v25.0/act_123/campaigns" (:url @captured)))
    (is (= "Bearer test-token" (get (:headers @captured) "Authorization")))))

(deftest call-honors-an-explicit-api-version
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"data\":[]}"})]
    (client/call! "/me/adaccounts" {:http-fn http-fn :token "t" :api-version "v24.0"})
    (is (str/starts-with? (:url @captured) "https://graph.facebook.com/v24.0"))))

(deftest call-throws-on-transport-non-2xx
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"Meta Marketing API request failed"
       (client/call! "/act_123/campaigns" {:http-fn (stub-http-fn 401 "{\"error\":{\"message\":\"bad token\"}}") :token "t"}))))

(deftest call-throws-on-graph-level-error-even-with-a-200-transport-status
  (testing "Graph API can return :error with an HTTP 200 -- must not be treated as success"
    (is (thrown-with-msg?
         #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
         #"Meta Marketing API request failed"
         (client/call! "/act_123/campaigns" {:http-fn (stub-http-fn 200 "{\"error\":{\"message\":\"oauth expired\",\"code\":190}}") :token "t"})))))

(deftest call-preserves-provider-native-error-fields
  (try
    (client/call! "/act_123/campaigns"
                 {:http-fn (stub-http-fn 400 "{\"error\":{\"message\":\"bad\",\"code\":100,\"fbtrace_id\":\"AbC123\"}}")
                  :token "t"})
    (is false "should have thrown")
    (catch #?(:clj clojure.lang.ExceptionInfo :cljs js/Error) e
      (is (= 100 (get-in (ex-data e) [:error :code])))
      (is (= "AbC123" (get-in (ex-data e) [:error :fbtrace_id]))))))

(deftest access-token-fails-closed-without-env-or-explicit-token
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"FACEBOOK_ACCESS_TOKEN is required"
       (client/call! "/me/adaccounts" {:http-fn (stub-http-fn 200 "{}")}))))
