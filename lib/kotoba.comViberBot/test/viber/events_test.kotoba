(ns viber.events-test
  (:require [clojure.test :refer [deftest is]]
            [viber.events :as ev]))

(def text-body
  {:event "message" :timestamp 1721000000000 :message_token 4912661846655238145
   :sender {:id "01234567890A=" :name "Taro"}
   :message {:type "text" :text "hello there"}})

(deftest text-message-event-shapes-a-user-text-message
  (is (= {:type :viber-text :user-id "01234567890A=" :message-token 4912661846655238145
          :text "hello there" :ts 1721000000000}
         (ev/text-message-event text-body))))

(deftest text-message-event-rejects-non-message-events
  (is (nil? (ev/text-message-event (assoc text-body :event "subscribed")))))

(deftest text-message-event-rejects-non-text-messages
  (is (nil? (ev/text-message-event (assoc-in text-body [:message :type] "picture")))))
