(ns facebook-graph.campaigns-test
  (:require [clojure.test :refer [deftest is]]
            [facebook-graph.campaigns :as campaigns]))

(defn- failing-http-fn [_req]
  (throw (ex-info "network should not have been called in dry-run" {})))

(deftest create-campaign-defaults-to-dry-run-and-never-calls-the-network
  (let [resp (campaigns/create-campaign! "act_123"
                                        {:name "Q3 launch" :objective "OUTCOME_TRAFFIC"}
                                        {:http-fn failing-http-fn :token "t"})]
    (is (= :dry-run (:mode resp)))
    (is (= :campaigns.create (:op resp)))
    (is (= "PAUSED" (get-in resp [:would-send :body :status])))
    (is (= [] (get-in resp [:would-send :body :special_ad_categories])))))

(deftest create-campaign-requires-name-and-objective
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"requires :name and :objective"
       (campaigns/create-campaign! "act_123" {:name "no objective"} {:http-fn failing-http-fn}))))

(deftest create-campaign-executes-for-real-only-when-dry-run-false
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"id\":\"c1\"}"})
        resp (campaigns/create-campaign! "act_123"
                                        {:name "Q3 launch" :objective "OUTCOME_TRAFFIC"}
                                        {:http-fn http-fn :token "t" :dry-run? false})]
    (is (= "c1" (:id resp)))
    (is (= :post (:method @captured)))))

(deftest pause-and-resume-are-dry-run-by-default
  (is (= :campaigns.pause (:op (campaigns/pause-campaign! "c1" {:http-fn failing-http-fn}))))
  (is (= :campaigns.resume (:op (campaigns/resume-campaign! "c1" {:http-fn failing-http-fn})))))

(deftest update-budget-fails-closed-without-an-explicit-ceiling
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"requires an explicit :budget-ceiling-minor-units"
       (campaigns/update-budget! "c1" 500000 :daily {:http-fn failing-http-fn}))))

(deftest update-budget-rejects-a-request-over-the-ceiling
  (is (thrown-with-msg?
       #?(:clj clojure.lang.ExceptionInfo :cljs js/Error)
       #"exceeds :budget-ceiling-minor-units"
       (campaigns/update-budget! "c1" 500000 :daily
                                {:http-fn failing-http-fn :budget-ceiling-minor-units 300000}))))

(deftest update-budget-dry-run-under-the-ceiling-succeeds-without-network
  (let [resp (campaigns/update-budget! "c1" 100000 :daily
                                      {:http-fn failing-http-fn :budget-ceiling-minor-units 300000})]
    (is (= :dry-run (:mode resp)))
    (is (= 100000 (get-in resp [:would-send :body :daily_budget])))))

(deftest validate-creative-checks-required-shape-without-a-network-call
  (is (:ok? (campaigns/validate-creative {:name "n" :object-story-spec {}})))
  (is (not (:ok? (campaigns/validate-creative {:name "n"})))))

(deftest operation-status-is-unsupported-for-non-insights-operations
  (let [resp (campaigns/operation-status {:operation-kind :campaign-mutation})]
    (is (not (:ok? resp)))
    (is (= :unsupported (:status resp)))))

(deftest operation-status-routes-insights-report-kind-to-the-real-poll-endpoint
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"async_status\":\"Job Completed\"}"})]
    (campaigns/operation-status {:operation-kind :insights-report :ref-id "run1" :http-fn http-fn :token "t"})
    (is (= "https://graph.facebook.com/v25.0/run1?fields=async_status,async_percent_completion" (:url @captured)))))
