(ns youtube.thumbnails-test
  (:require [clojure.test :refer [deftest is testing]]
            [youtube.thumbnails :as thumbnails]))

(deftest set-thumbnail-test
  (testing "happy path"
    (let [calls (atom [])
          stub (fn [req] (swap! calls conj req) {:status 200 :body "{}" :response-headers {}})
          result (thumbnails/set-thumbnail! "tok" "v1" (byte-array [1 2 3]) {:http-fn stub})]
      (is (nil? result))
      (is (.contains (:url (first @calls)) "videoId=v1"))
      (is (= "image/png" (get (:headers (first @calls)) "Content-Type")))))

  (testing "failure raises"
    (let [stub (fn [_] {:status 500 :body "err" :response-headers {}})]
      (is (thrown? clojure.lang.ExceptionInfo
                   (thumbnails/set-thumbnail! "tok" "v1" (byte-array [1]) {:http-fn stub}))))))
