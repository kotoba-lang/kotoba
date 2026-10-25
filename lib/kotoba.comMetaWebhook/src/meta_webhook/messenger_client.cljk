(ns meta-webhook.messenger-client
  "Messenger Platform Send API — send-side only (the webhook receiver's
  verify/parse live in `meta-webhook.signature`/`async-signature`/
  `messenger-events`; WhatsApp's own send-side is already covered by
  `kotoba-lang/tayori`'s `tayori.channel.whatsapp`, this ns is Messenger's
  counterpart since tayori has no Messenger channel).

  Portable `.cljc`, I/O injected (`:http-fn` `:json-write` `:json-read`
  `:creds {:page-access-token}`), same DI shape as `chatwork.client` /
  `tayori.channel.slack`."
  )

(defn send-message!
  "POST /v20.0/me/messages — `recipient-id` is a Messenger-scoped user id
  (from `meta-webhook.messenger-events`' `:user-id`), `text` the message
  body. `:messaging-type` defaults to \"RESPONSE\" (replying within Meta's
  24-hour standard messaging window; a message outside that window needs a
  different messaging_type/tag Meta's policy restricts — not handled here,
  caller's responsibility to pass the right `:messaging-type` for
  out-of-window sends)."
  [{:keys [http-fn json-write json-read creds]} {:keys [recipient-id text messaging-type]
                                                  :or {messaging-type "RESPONSE"}}]
  (let [token (:page-access-token creds)
        url   (str "https://graph.facebook.com/v20.0/me/messages?access_token=" token)
        resp  (http-fn {:url url :method :post
                         :headers {"Content-Type" "application/json"}
                         :body (json-write {:recipient {:id recipient-id}
                                             :message {:text text}
                                             :messaging_type messaging-type})})]
    (if (= 200 (:status resp))
      (json-read (:body resp))
      {:ok false :status (:status resp) :error (:body resp)})))
