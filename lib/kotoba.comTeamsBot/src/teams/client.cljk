(ns teams.client
  "Bot Framework Connector API — OAuth2 client-credentials token
  acquisition + send. Portable `.cljc`, I/O injected (`:http-fn`
  `:json-write` `:json-read` `:creds {:app-id :app-password}`).

  Auth is meaningfully different from every other client in this
  workspace: there is no static bot token. `fetch-token!` exchanges your
  bot's `app-id`/`app-password` (Azure AD App Registration → Certificates
  & secrets) for a short-lived (~1 hour) access token via OAuth2
  client-credentials, which `send-message!` then uses as a Bearer token.
  This library does NOT cache or auto-refresh the token — matching this
  workspace's convention of keeping stateful concerns (cursors, dedup
  sets, and now token expiry) in the CONSUMER, not the client library
  (`channels.discord`'s `:after-id` atom, `channels.slack`'s `:seen` atom
  are the same pattern) — a caller holds the fetched `{:token :expires-at}`
  and re-calls `fetch-token!` when it's stale.

  Acquiring `app-id`/`app-password` (the Azure AD App Registration, the
  Azure Bot resource, the messaging endpoint configuration) is OUT OF
  SCOPE here, same non-goal every other client in this workspace
  documents for its own credentials — this is simply a larger one-time
  setup than a static bot token."
  )

(def ^:private token-url
  "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token")

(defn fetch-token!
  "OAuth2 client-credentials grant. Returns `{:access-token :expires-in}`
  on success (`:expires-in` seconds, Microsoft's default ~3600), or
  `{:ok false :status :error}` on failure. `:http-fn` receives a
  `application/x-www-form-urlencoded` POST, NOT JSON (OAuth2 token
  endpoints uniformly use form encoding regardless of provider)."
  [{:keys [http-fn json-read creds]}]
  (let [body (str "grant_type=client_credentials"
                  "&client_id=" (:app-id creds)
                  "&client_secret=" (:app-password creds)
                  "&scope=" "https%3A%2F%2Fapi.botframework.com%2F.default")
        resp (http-fn {:url token-url :method :post
                        :headers {"Content-Type" "application/x-www-form-urlencoded"}
                        :body body})]
    (if (= 200 (:status resp))
      (let [{:keys [access_token expires_in]} (json-read (:body resp))]
        {:access-token access_token :expires-in expires_in})
      {:ok false :status (:status resp) :error (:body resp)})))

(defn send-message!
  "POST {service-url}/v3/conversations/{conversation-id}/activities --
  `text` as a plain message Activity. `service-url`/`conversation-id` come
  from the inbound Activity being replied to (`teams.events`'
  `:service-url`/`:conversation-id` -- Teams has no fixed send endpoint,
  ns docstring). `access-token` is a fetched OAuth2 token (`fetch-token!`),
  passed explicitly rather than via `:creds` since it's short-lived
  caller-managed state, not a static credential."
  [{:keys [http-fn json-write json-read]} {:keys [service-url conversation-id access-token text]}]
  (let [url  (str service-url "/v3/conversations/" conversation-id "/activities")
        resp (http-fn {:url url :method :post
                        :headers {"Authorization" (str "Bearer " access-token)
                                  "Content-Type" "application/json"}
                        :body (json-write {:type "message" :text text})})]
    (if (#{200 201} (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))
