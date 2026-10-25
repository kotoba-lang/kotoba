(ns youtube.channels-test
  (:require [clojure.test :refer [deftest is testing]]
            [youtube.channels :as channels]))

(defn- stub [body & {:keys [status] :or {status 200}}]
  (fn [_] {:status status :body body :response-headers {}}))

(def ^:private one-channel
  "{\"items\":[{\"id\":\"UC-expected\",\"snippet\":{\"title\":\"Yukkuri\"}}]}")

(deftest assert-channel-accepts-the-expected-one
  (is (= {:id "UC-expected" :title "Yukkuri"}
         (channels/assert-channel! "tok" "UC-expected" {:http-fn (stub one-channel)}))))

(deftest assert-channel-refuses-a-different-channel
  (testing "the whole point: publishing to the wrong channel cannot be undone by deleting"
    (let [e (try (channels/assert-channel!
                  "tok" "UC-expected"
                  {:http-fn (stub "{\"items\":[{\"id\":\"UC-other\",\"snippet\":{\"title\":\"Someone else\"}}]}")})
                 nil
                 (catch clojure.lang.ExceptionInfo ex ex))]
      (is (some? e))
      (is (= "UC-expected" (:expected (ex-data e))))
      (is (= [{:id "UC-other" :title "Someone else"}] (:found (ex-data e)))))))

(deftest assert-channel-refuses-ambiguity
  (testing "a token carrying two channels is refused even if one of them matches"
    (is (thrown? clojure.lang.ExceptionInfo
                 (channels/assert-channel!
                  "tok" "UC-expected"
                  {:http-fn (stub (str "{\"items\":[{\"id\":\"UC-expected\",\"snippet\":{\"title\":\"A\"}},"
                                       "{\"id\":\"UC-brand\",\"snippet\":{\"title\":\"B\"}}]}"))}))))
  (testing "and zero channels is refused, not treated as 'nothing to check'"
    (is (thrown? clojure.lang.ExceptionInfo
                 (channels/assert-channel! "tok" "UC-expected" {:http-fn (stub "{\"items\":[]}")})))))

(deftest list-mine-raises-on-non-200
  (is (thrown? clojure.lang.ExceptionInfo
               (channels/list-mine! "tok" {:http-fn (stub "nope" :status 403)}))))
