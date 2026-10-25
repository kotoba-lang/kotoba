(ns tiktok.client-test
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [tiktok.client :as tt]))

(defn- io-with [responses]
  (let [calls (atom [])]
    {:calls calls
     :io {:json-write identity
          :json-read identity
          :creds {:access-token "tok"}
          :http-fn (fn [req]
                     (swap! calls conj req)
                     (let [r (first @responses)]
                       (swap! responses rest)
                       r))}}))

(deftest rejects-an-unknown-privacy-level-before-sending
  (testing "a bad value fails locally rather than as an opaque API error"
    (is (thrown? #?(:clj clojure.lang.ExceptionInfo :cljs :default)
                 (tt/post-info {:title "t" :privacy-level "PUBLIC"})))))

(deftest defaults-to-the-safe-privacy-level
  (is (= "SELF_ONLY" (:privacy_level (tt/post-info {:title "t"})))))

(deftest init-pull-from-url-returns-publish-id
  (let [responses (atom [{:status 200 :body {"data" {"publish_id" "p-1"}
                                             "error" {"code" "ok"}}}])
        {:keys [calls io]} (io-with responses)]
    (is (= "p-1" (tt/init-pull-from-url! io {:title "t"
                                             :video-url "https://a/v.mp4"
                                             :privacy-level "SELF_ONLY"})))
    (let [body (:body (first @calls))]
      (is (= "PULL_FROM_URL" (get-in body [:source_info :source])))
      (is (= "https://a/v.mp4" (get-in body [:source_info :video_url]))))))

(deftest a-200-carrying-an-error-code-is-a-failure
  (testing "TikTok answers 200 with an error body; status alone is not success"
    (let [responses (atom [{:status 200
                            :body {"error" {"code" "spam_risk_too_many_posts"
                                            "message" "rate limited"}}}])
          {:keys [io]} (io-with responses)]
      (try
        (tt/init-pull-from-url! io {:title "t" :video-url "https://a/v.mp4"})
        (is false "should have thrown")
        (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) e
          (is (= "spam_risk_too_many_posts"
                 (get-in (ex-data e) [:error "code"]))))))))

(deftest init-file-upload-returns-both-handles
  (let [responses (atom [{:status 200
                          :body {"data" {"publish_id" "p-2"
                                         "upload_url" "https://upload/x"}
                                 "error" {"code" "ok"}}}])
        {:keys [calls io]} (io-with responses)
        r (tt/init-file-upload! io {:title "t" :video-size 1000})]
    (is (= {:publish-id "p-2" :upload-url "https://upload/x"} r))
    (testing "a single-chunk upload defaults chunk size to the whole file"
      (is (= 1000 (get-in (:body (first @calls)) [:source_info :chunk_size])))
      (is (= 1 (get-in (:body (first @calls)) [:source_info :total_chunk_count]))))))

(deftest chunk-upload-sends-content-range
  (let [responses (atom [{:status 200 :body {}}])
        {:keys [calls io]} (io-with responses)]
    (tt/upload-chunk! io "https://upload/x" (vec (repeat 100 0))
                      {:offset 0 :total 100})
    (is (= "bytes 0-99/100"
           (get-in (first @calls) [:headers "Content-Range"])))))

(deftest await-publish-distinguishes-complete-from-failed
  (testing "completion"
    (let [responses (atom [{:status 200 :body {"data" {"status" "PROCESSING_UPLOAD"}
                                               "error" {"code" "ok"}}}
                           {:status 200 :body {"data" {"status" "PUBLISH_COMPLETE"}
                                               "error" {"code" "ok"}}}])
          {:keys [io]} (io-with responses)]
      (is (= "PUBLISH_COMPLETE"
             (tt/await-publish io "p-1" {:sleep-fn (fn [_])})))))

  (testing "an init that ended in FAILED is not a publish"
    (let [responses (atom [{:status 200 :body {"data" {"status" "FAILED"}
                                               "error" {"code" "ok"}}}])
          {:keys [io]} (io-with responses)]
      (is (thrown? #?(:clj clojure.lang.ExceptionInfo :cljs :default)
                   (tt/await-publish io "p-1" {:sleep-fn (fn [_])}))))))
