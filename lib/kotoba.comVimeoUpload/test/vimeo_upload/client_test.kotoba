(ns vimeo-upload.client-test
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [vimeo-upload.client :as vm]))

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

(deftest create-video-requests-tus-and-returns-the-upload-link
  (let [responses (atom [{:status 201
                          :body {"uri" "/videos/123"
                                 "link" "https://vimeo.com/123"
                                 "upload" {"upload_link" "https://tus/123"}}}])
        {:keys [calls io]} (io-with responses)
        r (vm/create-video! io {:name "t" :description "d" :size 1000})]
    (is (= {:uri "/videos/123"
            :link "https://vimeo.com/123"
            :upload-link "https://tus/123"} r))
    (let [req (first @calls)]
      (testing "tus approach and exact size are declared up front"
        (is (= "tus" (get-in (:body req) [:upload :approach])))
        (is (= 1000 (get-in (:body req) [:upload :size]))))
      (testing "the API version rides in Accept, not the URL"
        (is (re-find #"version=3\.4" (get-in req [:headers "Accept"])))))))

(deftest upload-chunk-sends-the-tus-headers
  (let [responses (atom [{:status 204 :response-headers {"Upload-Offset" "500"}}])
        {:keys [calls io]} (io-with responses)
        next-offset (vm/upload-chunk! io "https://tus/1" (vec (repeat 500 0)) 0)]
    (is (= 500 next-offset))
    (let [h (:headers (first @calls))]
      (is (= "1.0.0" (get h "Tus-Resumable")))
      (is (= "0" (get h "Upload-Offset")))
      (is (= "application/offset+octet-stream" (get h "Content-Type"))))))

(deftest upload-offset-reads-the-servers-position
  (let [responses (atom [{:status 200 :response-headers {"upload-offset" "4096"}}])
        {:keys [io]} (io-with responses)]
    (is (= 4096 (vm/upload-offset io "https://tus/1")))))

(deftest a-chunk-that-does-not-advance-the-offset-is-an-error
  (testing "looping forever on a stuck server is worse than failing"
    (let [responses (atom [{:status 201 :body {"uri" "/videos/1"
                                               "upload" {"upload_link" "https://tus/1"}}}
                           {:status 200 :response-headers {"Upload-Offset" "0"}}
                           {:status 204 :response-headers {"Upload-Offset" "0"}}])
          {:keys [io]} (io-with responses)]
      (is (thrown? #?(:clj clojure.lang.ExceptionInfo :cljs :default)
                   (vm/upload-file! io {:name "t" :size 100}
                                    #?(:clj (byte-array 100)
                                       :cljs (js/Uint8Array. 100))
                                    {:chunk-size 50}))))))

(deftest upload-file-loops-on-the-server-offset
  (testing "resuming is correct because progress is read back, not counted locally"
    (let [responses (atom [{:status 201 :body {"uri" "/videos/7"
                                               "upload" {"upload_link" "https://tus/7"}}}
                           ;; server already holds 50 bytes from a previous attempt
                           {:status 200 :response-headers {"Upload-Offset" "50"}}
                           {:status 204 :response-headers {"Upload-Offset" "100"}}])
          {:keys [calls io]} (io-with responses)
          r (vm/upload-file! io {:name "t" :size 100}
                             #?(:clj (byte-array 100) :cljs (js/Uint8Array. 100))
                             {:chunk-size 50})]
      (is (= "/videos/7" (:uri r)))
      (testing "it resumed at 50 instead of re-sending the first chunk"
        (is (= "50" (get-in (last @calls) [:headers "Upload-Offset"])))
        (is (= 3 (count @calls)))))))

(deftest update-video-patches-metadata-independently
  (let [responses (atom [{:status 200 :body {"uri" "/videos/1" "name" "new"}}])
        {:keys [calls io]} (io-with responses)]
    (vm/update-video! io "/videos/1" {:name "new"})
    (is (= :patch (:method (first @calls))))
    (is (re-find #"/videos/1$" (:url (first @calls))))))
