(ns meta-webhook.instagram-client
  "Instagram Messaging API — send-side only (the webhook receiver's
  verify/parse live in `meta-webhook.signature`/`async-signature`/
  `instagram-events`). Portable `.cljc`, I/O injected (`:http-fn`
  `:json-write` `:json-read` `:creds {:ig-user-id :access-token}`), same DI
  shape as `meta-webhook.messenger-client` — different endpoint shape only
  (Instagram sends are scoped to the connected IG Business/Creator account
  id, `/​{ig-user-id}/messages`, not Messenger's fixed `/me/messages`)."
  )

(defn send-message!
  "POST /v21.0/{ig-user-id}/messages — `recipient-id` is an IGSID
  (Instagram-scoped user id, from `meta-webhook.instagram-events`'
  `:user-id`), `text` the message body."
  [{:keys [http-fn json-write json-read creds]} {:keys [recipient-id text]}]
  (let [{:keys [ig-user-id access-token]} creds
        url  (str "https://graph.facebook.com/v21.0/" ig-user-id
                  "/messages?access_token=" access-token)
        resp (http-fn {:url url :method :post
                        :headers {"Content-Type" "application/json"}
                        :body (json-write {:recipient {:id recipient-id}
                                            :message {:text text}})})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))
