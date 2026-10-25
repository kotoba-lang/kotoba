(ns viber.client
  "Viber REST Bot API — send + webhook (de)registration. Portable `.cljc`,
  I/O injected (`:http-fn` `:json-write` `:json-read` `:creds
  {:bot-token}`), same DI shape as `line-messaging.client`.

  Auth is `X-Viber-Auth-Token: <bot-token>` (from the Viber Admin Panel →
  your bot → API Info). This is the SAME token `viber.signature` uses to
  verify inbound webhooks (ns docstring there) — Viber has no separate app
  secret.

  Unlike WhatsApp/Messenger/Instagram/LINE (Meta/LY register your webhook
  URL by calling YOUR endpoint with a GET verification challenge), Viber's
  webhook registration is the OPPOSITE direction: YOUR backend calls
  Viber's `set_webhook` API with your URL. `set-webhook!` is that one-time
  (or whenever the URL changes) setup call — not something a Worker route
  handles inbound, a caller runs it once from a script/REPL."
  )

(def ^:private base-url "https://chatapi.viber.com/pa")

(defn- post! [{:keys [http-fn json-write json-read creds]} path payload]
  (let [resp (http-fn {:url (str base-url path) :method :post
                        :headers {"X-Viber-Auth-Token" (:bot-token creds)
                                  "Content-Type" "application/json"}
                        :body (json-write payload)})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn send-message!
  "POST /send_message -- `text` to `receiver` (a Viber user id, from
  `viber.events`' `:user-id`). Viber's own response envelope carries a
  `status`/`status_message` pair even on HTTP 200 (0 = success, nonzero =
  a Viber-level failure like an un-subscribed user) -- this fn does NOT
  re-interpret that envelope (callers wanting to distinguish
  \"HTTP failed\" from \"Viber rejected it\" read `:status`/:status_message`
  off the returned map themselves)."
  [io {:keys [receiver text]}]
  (post! io "/send_message" {:receiver receiver :type "text"
                              :sender {:name "manimani"} :text text}))

(defn set-webhook!
  "POST /set_webhook -- registers `url` as this bot's webhook endpoint.
  `event-types` defaults to just `[\"message\"]` (this workspace's channel
  adapters only consume inbound text messages, not
  subscribe/unsubscribe/delivered/seen events). Call once (or whenever the
  Worker URL changes) from a setup script -- not part of any request path."
  [io {:keys [url event-types] :or {event-types ["message"]}}]
  (post! io "/set_webhook" {:url url :event_types event-types}))
