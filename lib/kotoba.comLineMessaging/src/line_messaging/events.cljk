(ns line-messaging.events
  "Pure parsing of a LINE Messaging API webhook payload (already JSON-decoded
  by the caller -- this ns does no I/O and no signature verification, see
  `line-messaging.signature` / `line-messaging.async-signature` for that).

  Reference: https://developers.line.biz/en/reference/messaging-api/#webhook-event-objects")

(defn text-message-event
  "One raw LINE webhook event map -> {:type :user-id :reply-token :text :ts}
  or nil if it isn't a text message from a user (group/room source, non-text
  message types, and non-message events like `follow`/`postback` are all
  filtered out by the caller via `text-message-events`, not here -- this fn
  is the per-event predicate+shape so a caller can also use it standalone)."
  [{:keys [type replyToken timestamp source message] :as _event}]
  (when (and (= type "message") (= (:type message) "text") (= (:type source) "user"))
    {:type        :line-text
     :user-id     (:userId source)
     :reply-token replyToken
     :text        (:text message)
     :ts          timestamp}))

(defn text-message-events
  "A decoded webhook body `{:destination ... :events [...]}` -> vector of
  `text-message-event` results (group/room-sourced and non-text events
  dropped). `:destination` (the receiving bot's own user id) is intentionally
  not threaded through -- callers needing it read the raw body directly."
  [{:keys [events]}]
  (into [] (keep text-message-event) events))
