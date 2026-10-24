(ns meta-webhook.instagram-events
  "Pure parsing of an Instagram Messaging webhook payload (already
  JSON-decoded by the caller — this ns does no I/O and no signature
  verification, see `meta-webhook.signature`/`async-signature` for that,
  shared verbatim with WhatsApp/Messenger — Instagram Messaging is the same
  Meta Graph API webhook envelope, `:object \"instagram\"` instead of
  `\"page\"`/`\"whatsapp_business_account\"`).

  Same `entry[].messaging[]` shape as `meta-webhook.messenger-events` today
  (both products currently emit an identical event structure for plain text
  messages) — kept as a SEPARATE namespace rather than aliased, because
  Instagram's webhook also carries story-mention/story-reply events
  Messenger doesn't have; if this ns grows to normalize those too, the
  divergence from `messenger-events` won't require an awkward retrofit.

  Reference: https://developers.facebook.com/docs/messenger-platform/instagram/webhook-events")

(defn text-message-event
  "One raw Instagram `entry[].messaging[]` event -> {:type :user-id
  :message-id :text :ts} or nil if it isn't an inbound text message.
  `:is_echo` (a message the connected IG account itself sent, echoed back)
  and non-text messages (attachments/story-mentions only) are filtered out."
  [{:keys [sender message timestamp] :as _event}]
  (when (and message (:text message) (not (:is_echo message)))
    {:type       :instagram-text
     :user-id    (:id sender)
     :message-id (:mid message)
     :text       (:text message)
     :ts         timestamp}))

(defn text-message-events
  "A decoded webhook body `{:object \"instagram\" :entry [...]}` -> vector of
  `text-message-event` results (echoes, story-mentions, and attachment-only
  events dropped)."
  [{:keys [entry]}]
  (into [] (comp (mapcat :messaging) (keep text-message-event)) entry))
