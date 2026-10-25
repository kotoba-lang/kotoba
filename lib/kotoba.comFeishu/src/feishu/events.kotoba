(ns feishu.events
  "Pure parsing of a Feishu/Lark Event Subscription v2 webhook payload
  (already JSON-decoded by the caller -- signature/token verification is
  `feishu.signature`/`async-signature`, kept separate same as every other
  webhook-verify split in this workspace).

  Reference: https://open.feishu.cn/document/server-docs/event-subscription-guide/overview")

(defn url-verification-challenge
  "Feishu's one-time endpoint-setup handshake: a decoded body
  `{:type \"url_verification\" :challenge ... :token ...}` -> the
  `:challenge` string to echo back verbatim, or nil for any other event
  type. Caller wraps the return value as `{\"challenge\": <value>}` JSON
  -- this fn just extracts it."
  [{:keys [type challenge]}]
  (when (= type "url_verification") challenge))

(defn header-token
  "The Verification Token carried in a v2 event body's `header.token` --
  compare against your configured token via `feishu.signature/token-valid?`."
  [{:keys [header]}]
  (:token header))

(defn text-message-event
  "One decoded v2 event body (`{:header {...} :event {...}}`) ->
  {:type :user-id :chat-id :message-id :text :create-time} or nil if it
  isn't a plain text message (Feishu also delivers image/file/post/
  interactive-card messages this library doesn't normalize). Feishu
  double-encodes: `event.message.content` is itself a JSON string (e.g.
  `\"{\\\"text\\\":\\\"hi\\\"}\"`), not a nested map -- `json-read` is
  injected so this stays portable rather than hardcoding a JSON library
  for that inner decode. `:create-time` is `message.create_time`, epoch
  milliseconds as a STRING (Feishu's own convention, not this library's)."
  [json-read {:keys [header event]}]
  (when (= "im.message.receive_v1" (:event_type header))
    (let [{:keys [sender message]} event]
      (when (= "text" (:message_type message))
        {:type        :feishu-text
         :user-id     (get-in sender [:sender_id :open_id])
         :chat-id     (:chat_id message)
         :message-id  (:message_id message)
         :text        (:text (json-read (:content message)))
         :create-time (:create_time message)}))))
