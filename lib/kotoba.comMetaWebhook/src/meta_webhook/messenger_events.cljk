(ns meta-webhook.messenger-events
  "Pure parsing of a Messenger Platform webhook payload (already JSON-decoded
  by the caller — this ns does no I/O and no signature verification, see
  `meta-webhook.signature`/`async-signature` for that).

  Reference: https://developers.facebook.com/docs/messenger-platform/reference/webhook-events/messages")

(defn text-message-event
  "One raw Messenger `entry[].messaging[]` event -> {:type :user-id
  :message-id :text :ts} or nil if it isn't an inbound text message.
  `:is_echo` (a message YOUR page sent, echoed back) and non-text messages
  (attachments only) are filtered out — an echo counted as inbound would
  make the page reply to its own messages."
  [{:keys [sender message timestamp] :as _event}]
  (when (and message (:text message) (not (:is_echo message)))
    {:type       :messenger-text
     :user-id    (:id sender)
     :message-id (:mid message)
     :text       (:text message)
     :ts         timestamp}))

(defn text-message-events
  "A decoded webhook body `{:object \"page\" :entry [...]}` -> vector of
  `text-message-event` results (echoes, postbacks, and attachment-only
  events dropped)."
  [{:keys [entry]}]
  (into [] (comp (mapcat :messaging) (keep text-message-event)) entry))
