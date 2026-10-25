(ns discord.client
  "Discord Bot API client — channel message list + send, the two operations
  a channel ingress/egress adapter needs. Portable `.cljc`, I/O injected
  (`:http-fn` `:json-write` `:json-read` `:creds`), same DI shape as
  `chatwork.client` / `x.client`.

  Not `kotoba-lang/com-discord` — that repo is an unrelated clean-room
  re-implementation of the Discord platform's own backend infrastructure
  (same trap as `com-line-api` vs `com-line-messaging`); this one is a
  client for the real, hosted Discord Bot API.

  Auth is `Authorization: Bot <token>` in `:creds {:bot-token \"...\"}` (a
  bot application token, from the Discord Developer Portal → your
  application → Bot → Token). Acquiring the token (creating the
  application, inviting the bot to a server with the right OAuth2 scopes/
  permissions) is OUT OF SCOPE here, same non-goal `com-gmail`/`com-x`
  document for their own tokens.

  Scope: REST polling (`GET .../messages`) only, not the Gateway WebSocket
  real-time API Discord bots more commonly use — this matches the
  poll-based `gw/Channel` shape every other channel adapter in this
  workspace already uses (`chatwork.client`/`x.client`), and avoids the
  Gateway's own complexity (persistent WS connection, heartbeats, sharding)
  for a personal-scale single-channel watch. A consumer needing real-time
  delivery or multi-channel/multi-guild scale should use the Gateway
  instead — not built here.")

(def ^:private base-url "https://discord.com/api/v10")

(defn- auth-header [creds]
  {"Authorization" (str "Bot " (:bot-token creds))})

(defn- get! [{:keys [http-fn json-read creds]} path]
  (let [resp (http-fn {:url (str base-url path) :method :get :headers (auth-header creds)})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn- post! [{:keys [http-fn json-write json-read creds]} path payload]
  (let [resp (http-fn {:url (str base-url path) :method :post
                        :headers (assoc (auth-header creds) "Content-Type" "application/json")
                        :body (json-write payload)})]
    (if (#{200 201} (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn list-messages
  "GET /channels/{channel-id}/messages -- recent messages, Discord's own
  newest-first order. `:after`(message-id, optional) limits to messages
  after that id (incremental fetch). `:limit`(default 50, Discord max 100).
  Returns the raw message vector, or [] on failure (fail-open, matches
  `x.client/search-recent-mentions`'s posture for a polling fetch)."
  [io {:keys [channel-id after limit] :or {limit 50}}]
  (let [q   (cond-> (str "?limit=" limit) after (str "&after=" after))
        res (get! io (str "/channels/" channel-id "/messages" q))]
    (if (vector? res) res [])))

(defn send-message!
  "POST /channels/{channel-id}/messages -- `text` as plain message content."
  [io {:keys [channel-id text]}]
  (post! io (str "/channels/" channel-id "/messages") {:content text}))
