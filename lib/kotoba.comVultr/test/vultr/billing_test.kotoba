(ns vultr.billing-test
  (:require [clojure.test :refer [deftest is]]
            [vultr.billing :as billing]))

(deftest list-history-hits-the-billing-history-path-with-no-query-by-default
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"billing_history\":[]}"})]
    (is (= [] (billing/list-history {:http-fn http-fn :token "t"})))
    (is (re-find #"/billing/history$" (:url @captured)))))

(deftest list-history-passes-cursor-and-per-page-through
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"billing_history\":[]}"})]
    (billing/list-history {:http-fn http-fn :token "t" :cursor "abc" :per-page 250})
    (is (re-find #"cursor=abc" (:url @captured)))
    (is (re-find #"per_page=250" (:url @captured)))))

(deftest list-invoices-hits-the-billing-invoices-path
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"billing_invoices\":[{\"id\":9}]}"})]
    (is (= [{:id 9}] (billing/list-invoices {:http-fn http-fn :token "t"})))
    (is (re-find #"/billing/invoices$" (:url @captured)))))

(deftest get-invoice-hits-the-invoice-by-id
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"billing_invoice\":{\"id\":9}}"})]
    (is (= {:id 9} (billing/get-invoice 9 {:http-fn http-fn :token "t"})))
    (is (re-find #"/billing/invoices/9$" (:url @captured)))))

(deftest invoice-items-hits-the-invoice-items-path
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"invoice_items\":[]}"})]
    (is (= [] (billing/invoice-items 9 {:http-fn http-fn :token "t"})))
    (is (re-find #"/billing/invoices/9/items$" (:url @captured)))))
