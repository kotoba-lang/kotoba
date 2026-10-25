(ns feishu.client
  "Feishu/Lark Open Platform API -- tenant token acquisition + send +
  list. Portable `.cljc`, I/O injected (`:http-fn` `:json-write`
  `:json-read` `:creds {:app-id :app-secret}`).

  Auth is a short-lived (~2 hour) `tenant_access_token`, obtained by
  exchanging your app's `app-id`/`app-secret` (Feishu Open Platform
  Console -> your app -> Credentials & Basic Info). Same non-caching
  convention as `teams.client/fetch-token!` (ns docstring there) -- this
  library does not cache or auto-refresh; a caller holds the fetched
  `{:token :expires-in}` and re-calls `fetch-tenant-access-token!` when
  stale.")

(def ^:private token-url
  "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal")

(def ^:private messages-url
  "https://open.feishu.cn/open-apis/im/v1/messages")

(defn fetch-tenant-access-token!
  "Returns `{:tenant-access-token :expire}` (`:expire` seconds) on
  success, or `{:ok false :status :error}` on failure. Feishu's own
  envelope always returns HTTP 200 even on auth failure, distinguishing
  success via a `code`/`msg` pair inside the body -- this fn treats
  `code != 0` as failure too (not just non-200), unlike this workspace's
  usual bare HTTP-status check, because relying on HTTP status alone
  would silently treat a bad app-secret as success here."
  [{:keys [http-fn json-write json-read creds]}]
  (let [resp (http-fn {:url token-url :method :post
                        :headers {"Content-Type" "application/json"}
                        :body (json-write {:app_id (:app-id creds) :app_secret (:app-secret creds)})})]
    (if (= 200 (:status resp))
      (let [{:keys [code msg tenant_access_token expire]} (json-read (:body resp))]
        (if (= 0 code)
          {:tenant-access-token tenant_access_token :expire expire}
          {:ok false :status :error :error msg}))
      {:ok false :status (:status resp) :error (:body resp)})))

(defn send-message!
  "POST /open-apis/im/v1/messages -- `text` to `receive-id` (an open_id or
  chat_id, from `feishu.events`' `:user-id`/`:chat-id`; `receive-id-type`
  defaults to `\"open_id\"`). `tenant-access-token` is a fetched token
  (`fetch-tenant-access-token!`), passed explicitly rather than via
  `:creds` since it's short-lived caller-managed state, matching
  `teams.client/send-message!`'s `access-token` param."
  [{:keys [http-fn json-write json-read]}
   {:keys [receive-id receive-id-type text tenant-access-token] :or {receive-id-type "open_id"}}]
  (let [url  (str messages-url "?receive_id_type=" receive-id-type)
        resp (http-fn {:url url :method :post
                        :headers {"Authorization" (str "Bearer " tenant-access-token)
                                  "Content-Type" "application/json"}
                        :body (json-write {:receive_id receive-id
                                            :msg_type   "text"
                                            :content    (json-write {:text text})})})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))
