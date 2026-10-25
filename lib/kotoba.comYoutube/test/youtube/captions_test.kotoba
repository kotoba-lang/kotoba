(ns youtube.captions-test
  (:require [clojure.test :refer [deftest is testing]]
            [youtube.captions :as captions]))

(deftest multipart-body-test
  (let [srt (.getBytes "1\n00:00:00,000 --> 00:00:01,000\nhello\n" "UTF-8")
        body (captions/multipart-body {:snippet {:videoId "v1" :language "ja" :name "n" :isDraft false}}
                                      srt "BOUND")
        body-str (String. body "UTF-8")]
    (is (.startsWith body-str "--BOUND\r\n"))
    (is (.contains body-str "Content-Type: application/json"))
    (is (.contains body-str "Content-Type: application/x-subrip"))
    (is (.endsWith body-str "--BOUND--\r\n"))
    (is (.contains body-str "hello"))))

(deftest insert-caption-test
  (testing "happy path"
    (let [calls (atom [])
          stub (fn [req] (swap! calls conj req) {:status 200 :body "{}" :response-headers {}})
          result (captions/insert-caption! "tok" {:youtube-video-id "v1" :lang "ja" :name "n"}
                                           (byte-array [1 2 3]) {:http-fn stub :boundary "B"})]
      (is (nil? result))
      (is (= :post (:method (first @calls))))
      (is (= "multipart/related; boundary=B" (get (:headers (first @calls)) "Content-Type")))))

  (testing "failure raises"
    (let [stub (fn [_] {:status 400 :body "err" :response-headers {}})]
      (is (thrown? clojure.lang.ExceptionInfo
                   (captions/insert-caption! "tok" {:youtube-video-id "v1" :lang "ja" :name "n"}
                                             (byte-array [1]) {:http-fn stub}))))))
