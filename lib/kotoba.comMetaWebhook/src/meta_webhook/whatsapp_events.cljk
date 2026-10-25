(ns meta-webhook.whatsapp-events
  "Pure parsing of a WhatsApp Business Cloud API webhook payload (already
  JSON-decoded by the caller — this ns does no I/O and no signature
  verification, see `meta-webhook.signature`/`async-signature` for that).

  Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples")

(defn- change-messages [change]
  (get-in change [:value :messages]))

(defn text-message-event
  "One raw WhatsApp message map (`entry[].changes[].value.messages[]`) ->
  {:type :user-id :message-id :text :ts} or nil if it isn't a text message
  (WhatsApp also sends image/audio/location/status-update payloads this
  library doesn't normalize)."
  [{:keys [type from id timestamp text] :as _msg}]
  (when (= type "text")
    {:type       :whatsapp-text
     :user-id    from
     :message-id id
     :text       (:body text)
     :ts         timestamp}))

(defn text-message-events
  "A decoded webhook body `{:object ... :entry [...]}` -> vector of
  `text-message-event` results (non-text messages and status-update-only
  changes dropped)."
  [{:keys [entry]}]
  (into [] (comp (mapcat :changes) (mapcat change-messages) (keep text-message-event)) entry))
