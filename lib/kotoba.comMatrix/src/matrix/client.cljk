(ns matrix.client
  "Matrix Client-Server API client — room sync (poll-based) + send, the two
  operations a channel ingress/egress adapter needs. Portable `.cljc`, I/O
  injected (`:http-fn` `:json-write` `:json-read` `:creds`), same DI shape
  as `chatwork.client` / `mattermost.client`.

  Auth is `Authorization: Bearer <access_token>` in `:creds
  {:access-token \"...\"}` (from a Matrix login — either interactive
  password login or an admin-issued token). Acquiring the token is OUT OF
  SCOPE here, same non-goal every other client in this workspace documents.

  Self-hosted/federated: like Mattermost, there is no single fixed API
  host — `:creds` also carries `:base-url` (your homeserver URL, e.g.
  `https://matrix.org` or a self-hosted Synapse/Dendrite/Conduit
  deployment).

  `sync!` uses Matrix's own `/sync` endpoint but with `timeout=0`
  (non-blocking, returns immediately with whatever's new) rather than
  Matrix's native long-polling — this matches the poll-based `gw/Channel`
  convention every other channel adapter in this workspace uses (a caller
  re-polls at its own interval) and avoids holding an HTTP connection open
  for the duration of a long-poll, which the synchronous `:http-fn`
  contract every client in this workspace shares isn't shaped for."
  )

(defn- auth-header [creds]
  {"Authorization" (str "Bearer " (:access-token creds))})

(defn- get! [{:keys [http-fn json-read creds]} path]
  (let [resp (http-fn {:url (str (:base-url creds) path) :method :get :headers (auth-header creds)})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn- put! [{:keys [http-fn json-write json-read creds]} path payload]
  (let [resp (http-fn {:url (str (:base-url creds) path) :method :put
                        :headers (assoc (auth-header creds) "Content-Type" "application/json")
                        :body (json-write payload)})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn sync!
  "GET /_matrix/client/v3/sync?timeout=0&since=... -- non-blocking poll
  (ns docstring). `:since`(a `:next-batch` token from a prior call,
  optional -- omit for the first call, which returns full current state).
  Flattens `m.room.message` events out of every joined room's timeline
  into a single vector, each event tagged with `:room-id` (the room's own
  map key, whatever type the caller's `:json-read` produced it as --
  iterating a map's own entries needs no separate id-type reconciliation,
  unlike `mattermost.client/list-messages`' `:order`/`:posts` cross-
  reference). Returns `{:next-batch :events}`; on failure, `:next-batch`
  is echoed back unchanged (so a caller's stored cursor doesn't regress)
  and `:events` is `[]` (fail-open)."
  [io {:keys [since]}]
  (let [q   (str "?timeout=0" (when since (str "&since=" since)))
        res (get! io (str "/_matrix/client/v3/sync" q))]
    (if (false? (:ok res))
      {:next-batch since :events []}
      (let [rooms  (get-in res [:rooms :join])
            events (for [[room-id room] rooms
                         event (get-in room [:timeline :events])
                         :when (= "m.room.message" (:type event))]
                     (assoc event :room-id (name room-id)))]
        {:next-batch (:next_batch res) :events (vec events)}))))

(def ^:private txn-counter (atom 0))

(defn- next-txn-id []
  ;; Matrix only requires a txnId unique per access token -- a monotonic
  ;; counter satisfies that without any platform-specific time/random call
  ;; (portable :clj/:cljs, no reader-conditional needed).
  (str "kotoba-matrix-" (swap! txn-counter inc)))

(defn send-message!
  "PUT /_matrix/client/v3/rooms/{room-id}/send/m.room.message/{txnId} --
  `text` as an `m.text` message body."
  [io {:keys [room-id text]}]
  (put! io (str "/_matrix/client/v3/rooms/" room-id "/send/m.room.message/" (next-txn-id))
        {:msgtype "m.text" :body text}))
