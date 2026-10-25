(ns vultr.account-test
  (:require [clojure.test :refer [deftest is]]
            [vultr.account :as account]))

(deftest get-account-hits-the-account-endpoint-and-unwraps-the-envelope
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req)
                  {:status 200 :body "{\"account\":{\"balance\":-12.34,\"pending_charges\":5.67}}"})]
    (is (= {:balance -12.34 :pending_charges 5.67}
           (account/get-account {:http-fn http-fn :token "t"})))
    (is (re-find #"/account$" (:url @captured)))))
