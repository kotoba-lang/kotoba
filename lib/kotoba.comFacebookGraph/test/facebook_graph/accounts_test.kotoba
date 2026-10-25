(ns facebook-graph.accounts-test
  (:require [clojure.test :refer [deftest is]]
            [facebook-graph.accounts :as accounts]))

(deftest list-accounts-requests-the-expected-fields
  (let [captured (atom nil)
        http-fn (fn [req] (reset! captured req) {:status 200 :body "{\"data\":[]}"})]
    (accounts/list-accounts {:http-fn http-fn :token "t"})
    (is (= "https://graph.facebook.com/v25.0/me/adaccounts?fields=account_id,name,account_status,currency,timezone_name"
          (:url @captured)))))

(deftest capabilities-get-never-claims-production-write
  (let [caps (:operations (accounts/capabilities-get))]
    (is (every? #(not= :production-write (:status %)) (vals caps))
        "no operation may claim production-write without a real receipt backing it")))

(deftest capabilities-marks-creatives-validate-as-schema-only-not-a-live-call
  (is (= :schema-validation-only (get-in accounts/capabilities [:creatives.validate :status]))))
