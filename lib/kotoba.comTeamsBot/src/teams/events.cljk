(ns teams.events
  "Pure parsing of a Bot Framework webhook Activity payload (already
  JSON-decoded by the caller — this ns does no I/O and no JWT
  verification, see `teams.jwt`/`jwt-verify` for that). One Activity per
  webhook POST, like Viber's one-event-per-call shape (not a
  Meta-style `entry[].messaging[]` batch).

  Reference: https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference")

(defn text-message-event
  "One decoded Activity -> {:type :user-id :text :ts :conversation-id
  :service-url} or nil if it isn't an inbound text message (`type` other
  than \"message\", or no `text` -- Teams also sends
  conversationUpdate/typing/etc. activity types this library doesn't
  normalize). `:conversation-id` + `:service-url` are BOTH required to
  reply (`teams.client/send-message!`'s `POST
  {service-url}/v3/conversations/{conversation-id}/activities`) -- unlike
  every other channel in this workspace, Teams' send endpoint isn't a
  fixed URL, it's carried in each inbound Activity."
  [{:keys [type text timestamp from conversation serviceUrl]}]
  (when (and (= type "message") (not-empty text))
    {:type            :teams-text
     :user-id         (:id from)
     :text            text
     :ts              timestamp
     :conversation-id (:id conversation)
     :service-url     serviceUrl}))
