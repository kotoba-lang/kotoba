(ns line-messaging.client
  "LINE Messaging API send-side client (https://developers.line.biz/en/reference/messaging-api/)
  -- push + reply only, the two operations an outbound channel adapter needs.
  Portable `.cljc`, I/O injected the same DI shape as `chatwork.client` /
  `tayori.channel.slack`: `(f {:http-fn :json-write :json-read :creds})`.

  Auth: a long-lived channel access token (LINE Developers Console → Messaging
  API → Channel access token), `:creds {:channel-access-token \"...\"}`.
  Distinct from the channel SECRET `line-messaging.signature` uses to verify
  inbound webhooks -- the two are different values from the same console
  page, do not conflate them.

  `reply!` requires a `replyToken` from a just-received webhook event and
  expires ~1 minute after receipt (LINE's own limit) -- a poll-based consumer
  (checks inbox every N seconds/minutes rather than reacting to the webhook
  synchronously) will usually find the reply token already expired by the
  time it decides to respond, so `push!` (uses the durable `userId` instead,
  no expiry, but consumes the account's monthly push-message quota on the
  free tier) is the one a delayed/batched reply flow should use.")

(def ^:private api-base "https://api.line.me/v2/bot/message")

(defn- text-messages [body]
  (mapv (fn [t] {:type "text" :text t}) (if (sequential? body) body [body])))

(defn- post! [{:keys [http-fn json-write json-read creds]} path payload]
  (let [resp (http-fn {:url (str api-base path) :method :post
                        :headers {"Authorization" (str "Bearer " (:channel-access-token creds))
                                  "Content-Type"  "application/json"}
                        :body (json-write payload)})]
    (if (= 200 (:status resp))
      (or (some-> (:body resp) not-empty json-read) {})
      {:ok false :status (:status resp) :error (:body resp)})))

(defn push!
  "POST /message/push -- `to` is a LINE userId (from `line-messaging.events`'
  `:user-id`). `body` is a string or a collection of strings (LINE allows up
  to 5 message objects per call; each string becomes one `{:type \"text\"}`)."
  [io {:keys [to body]}]
  (post! io "/push" {:to to :messages (text-messages body)}))

(defn reply!
  "POST /message/reply -- `reply-token` from the webhook event being answered.
  Expires ~1 minute after LINE sent the webhook; see ns docstring for why
  `push!` is usually the right choice for a poll-based consumer instead."
  [io {:keys [reply-token body]}]
  (post! io "/reply" {:replyToken reply-token :messages (text-messages body)}))
