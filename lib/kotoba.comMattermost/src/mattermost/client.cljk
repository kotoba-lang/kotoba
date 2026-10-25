(ns mattermost.client
  "Mattermost REST API v4 client — channel message list + send, the two
  operations a channel ingress/egress adapter needs. Portable `.cljc`, I/O
  injected (`:http-fn` `:json-write` `:json-read` `:creds`), same DI shape
  as `chatwork.client` / `discord.client`.

  Auth is `Authorization: Bearer <token>` in `:creds {:bot-token \"...\"}`
  (a Personal Access Token or bot account token, from a Mattermost
  System Console → Integrations → Bot Accounts, or a user's own PAT under
  Account Settings → Security). Acquiring the token is OUT OF SCOPE here,
  same non-goal every other client in this workspace documents.

  Self-hosted: unlike every other client in this workspace, Mattermost has
  no single fixed API host — `:creds` also carries `:base-url` (e.g.
  `https://mattermost.example.com`), the deployment's own server URL."
  )

(defn- base-url [creds] (str (:base-url creds) "/api/v4"))

(defn- auth-header [creds]
  {"Authorization" (str "Bearer " (:bot-token creds))})

(defn- get! [{:keys [http-fn json-read creds]} path]
  (let [resp (http-fn {:url (str (base-url creds) path) :method :get :headers (auth-header creds)})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn- post! [{:keys [http-fn json-write json-read creds]} path payload]
  (let [resp (http-fn {:url (str (base-url creds) path) :method :post
                        :headers (assoc (auth-header creds) "Content-Type" "application/json")
                        :body (json-write payload)})]
    (if (#{200 201} (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn list-messages
  "GET /channels/{channel-id}/posts -- recent posts. `:since`(Unix ms,
  optional) limits to posts created after that time (incremental fetch).
  Mattermost's response shape is `{:order [id ...] :posts {id {...}}}`
  (posts keyed by id, `:order` gives newest-first sequence) -- this fn
  flattens that into a plain newest-first vector of post maps, or [] on
  failure (fail-open, matches `discord.client/list-messages`'s posture).

  `:posts`' keys are dynamic (post ids), so whether they land as strings or
  keywords depends entirely on the caller's `:json-read` (`:key-fn keyword`
  keyword-ifies EVERY object key including dynamic ones, `:key-fn identity`
  keeps them as strings) -- `:order`'s entries are always plain JSON
  strings, so a keyword-keyed `:json-read` needs an explicit `(keyword id)`
  lookup here or every post silently drops. Tries the keyword form first
  (matches this workspace's `#(json/read-str % :key-fn keyword)`
  convention every other channel client uses), falls back to the raw
  string id."
  [io {:keys [channel-id since]}]
  (let [path (str "/channels/" channel-id "/posts" (when since (str "?since=" since)))
        {:keys [ok order posts]} (get! io path)]
    ;; `get!` returns either the raw success body (no :ok key, so `ok` here
    ;; is nil/truthy-absent) or an explicit {:ok false ...} failure map --
    ;; `(false? ok)` is the only reliable discriminator (both shapes are
    ;; maps, `map?` alone can't tell them apart).
    (if (or (false? ok) (nil? order) (nil? posts))
      []
      (into [] (keep (fn [id] (or (get posts (keyword id)) (get posts id)))) order))))

(defn send-message!
  "POST /posts -- `text` as plain post message."
  [io {:keys [channel-id text]}]
  (post! io "/posts" {:channel_id channel-id :message text}))
