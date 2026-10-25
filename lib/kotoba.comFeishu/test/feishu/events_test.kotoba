(ns feishu.events-test
  (:require [clojure.test :refer [deftest testing is]]
            [feishu.events :as events]))

(deftest url-verification-challenge-test
  (testing "url_verification type extracts the challenge"
    (is (= "chal-123" (events/url-verification-challenge
                        {:type "url_verification" :challenge "chal-123" :token "tok"}))))
  (testing "other event types -> nil"
    (is (nil? (events/url-verification-challenge {:type "event_callback"})))))

(deftest header-token-test
  (is (= "verify-tok" (events/header-token {:header {:token "verify-tok" :event_type "im.message.receive_v1"}}))))

(defn- fake-json-read [s]
  (case s
    "{\"text\":\"hello\"}" {:text "hello"}
    (throw (ex-info "unexpected content" {:s s}))))

(deftest text-message-event-test
  (testing "text message -> normalized event"
    (is (= {:type :feishu-text
            :user-id "ou_abc"
            :chat-id "oc_xyz"
            :message-id "om_1"
            :text "hello"
            :create-time "1700000000000"}
           (events/text-message-event
            fake-json-read
            {:header {:event_type "im.message.receive_v1"}
             :event {:sender {:sender_id {:open_id "ou_abc"}}
                     :message {:message_id "om_1" :chat_id "oc_xyz"
                               :message_type "text" :content "{\"text\":\"hello\"}"
                               :create_time "1700000000000"}}}))))
  (testing "non-text message -> nil"
    (is (nil? (events/text-message-event
               fake-json-read
               {:header {:event_type "im.message.receive_v1"}
                :event {:sender {:sender_id {:open_id "ou_abc"}}
                        :message {:message_id "om_2" :chat_id "oc_xyz" :message_type "image"}}}))))
  (testing "non-message event type -> nil"
    (is (nil? (events/text-message-event
               fake-json-read
               {:header {:event_type "im.chat.member.bot.added_v1"} :event {}})))))
