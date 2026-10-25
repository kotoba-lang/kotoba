(ns viber.events
  "Pure parsing of a Viber webhook payload (already JSON-decoded by the
  caller — this ns does no I/O and no signature verification, see
  `viber.signature`/`async-signature` for that).

  Unlike LINE/Meta products, a Viber webhook POST carries ONE event object
  per request (not a batch/array) — `text-message-event` is the whole
  parse, no `events[]` to flatten.

  Reference: https://developers.viber.com/docs/api/rest-bot-api/#receive-message-from-user")

(defn text-message-event
  "One decoded Viber webhook body -> {:type :user-id :message-token :text
  :ts} or nil if it isn't an inbound text message (`event` other than
  \"message\", or a non-text `message.type` -- Viber also sends
  picture/video/contact/sticker message types this library doesn't
  normalize)."
  [{:keys [event sender message timestamp message_token]}]
  (when (and (= event "message") (= (:type message) "text"))
    {:type           :viber-text
     :user-id        (:id sender)
     :message-token  message_token
     :text           (:text message)
     :ts             timestamp}))
