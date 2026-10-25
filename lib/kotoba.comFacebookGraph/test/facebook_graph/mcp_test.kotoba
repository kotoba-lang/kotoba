(ns facebook-graph.mcp-test
  (:require [clojure.test :refer [deftest is]]
            [facebook-graph.mcp :as mcp]))

(defn- failing-http-fn [_req]
  (throw (ex-info "network should not have been called" {})))

(deftest tools-lists-all-ten-adr-0023-contract-operations
  (is (= 10 (count mcp/tools)))
  (is (= #{"facebook_graph.accounts.list" "facebook_graph.capabilities.get"
          "facebook_graph.campaigns.list" "facebook_graph.campaigns.create"
          "facebook_graph.campaigns.pause" "facebook_graph.campaigns.resume"
          "facebook_graph.budgets.update" "facebook_graph.creatives.validate"
          "facebook_graph.metrics.report" "facebook_graph.operations.status"}
        (set (map :name mcp/tools)))))

(deftest call-tool-dispatches-capabilities-get-without-a-network-call
  (let [resp (mcp/call-tool "facebook_graph.capabilities.get" {})]
    (is (:ok? resp))
    (is (= "kotoba-lang/com-facebook-graph" (get-in resp [:result :provider])))))

(deftest call-tool-dispatches-campaigns-create-as-a-dry-run-by-default
  (let [resp (mcp/call-tool "facebook_graph.campaigns.create"
                           {:ad-account-id "act_123" :name "n" :objective "OUTCOME_TRAFFIC"
                            :http-fn failing-http-fn :token "t"})]
    (is (:ok? resp))
    (is (= :dry-run (get-in resp [:result :mode])))))

(deftest call-tool-converts-string-budget-kind-to-a-keyword
  (let [resp (mcp/call-tool "facebook_graph.budgets.update"
                           {:campaign-id "c1" :budget-minor-units 1000 :budget-kind "daily"
                            :budget-ceiling-minor-units 5000 :http-fn failing-http-fn :token "t"})]
    (is (:ok? resp) (str resp))
    (is (= :dry-run (get-in resp [:result :mode])))))

(deftest call-tool-returns-a-typed-error-instead-of-throwing-for-an-unknown-tool
  (let [resp (mcp/call-tool "facebook_graph.does-not-exist" {})]
    (is (not (:ok? resp)))
    (is (= "Unknown tool" (get-in resp [:error :message])))))

(deftest call-tool-surfaces-a-budget-ceiling-violation-as-a-typed-error-not-a-throw
  (let [resp (mcp/call-tool "facebook_graph.budgets.update"
                           {:campaign-id "c1" :budget-minor-units 999999 :budget-kind "daily"
                            :budget-ceiling-minor-units 100 :http-fn failing-http-fn :token "t"})]
    (is (not (:ok? resp)))
    (is (re-find #"exceeds" (get-in resp [:error :message])))))
