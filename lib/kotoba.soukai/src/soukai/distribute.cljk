(ns soukai.distribute
  "REAL Resend-based Distributor for `soukai.noticeport`'s `:convocation/send` —
  the soukai analog of `koyomi.distribute`. `soukai.noticeport/mock-
  noticeport` stays the runnable, offline DEFAULT; `resend-noticeport` here
  is an opt-in real `NoticeTarget`, swapped in only via `soukai.operation/
  build`'s `:noticeport` opt — never the default, same discipline as
  `koyomi.distribute/resend-scheduleport` and `koyomi.kotoba/kotoba-store`
  (a real backend that's still a constructor call away, not an always-on
  side effect).

  Only this namespace touches the network (`java.net.http`) or
  `RESEND_API_KEY` — `soukai.noticeport` (notice-text building), `mail.*`,
  and `mailer.*` all stay pure, mirroring `koyomi.distribute`'s own charter
  verbatim (\"Only this namespace touches the network ... mail.* and
  mailer.* stay pure\"). `jvm-http-fn` below is a byte-for-byte port of
  `koyomi.distribute/jvm-http-fn` (same `{:url :method :headers :body} ->
  {:status :body}` convention) so `send-notice!` can be tested with a
  stubbed `:http-fn` instead of a real Resend call.

  `kotoba-lang/mailer`'s `request` builds the Resend envelope (from/to/
  subject/text/html + auth capability) — this ns does NOT reimplement that.
  Unlike `koyomi.distribute` (which attaches a separately-built ICS string
  as a `text/calendar` attachment, since a calendar invite is a distinct
  artifact from the share notification), soukai has no separate
  calendar-invite artifact: `soukai.noticeport/notice-text`'s already-built
  plain-text 招集通知 IS the email body directly, so no `:attachments`
  field is added onto `mailer.core/request`'s envelope at all.

  Recipients-are-operator-supplied (the one real design decision here, see
  `resend-noticeport`'s docstring): soukai's data model deliberately keeps
  `shareholder-id` (the ground-fact identifier `soukai.store`'s snapshot/
  vote facts use) and email address separate — there is no
  shareholder-id → email mapping anywhere in `soukai.model`/`soukai.store`
  (verified — grepping `email` across `src/soukai/*.cljc` is a zero hit).
  Wiring a real company's shareholder registry (which, unlike koyomi's ICS
  attendees, is a legally significant record subject to its own accuracy/
  privacy obligations under 会社法) into this actor is a separate, bigger
  scope decision, not appropriate to bolt on silently as a byproduct of
  wiring up a mail sender — so unlike `koyomi.distribute/share-message`'s
  reuse of `:calendar/attendees` as the Resend `to` list, this ns's
  `notice-message` takes an explicit `recipients` argument the operator
  supplies at `resend-noticeport` construction time, never derived from the
  meeting/snapshot/votes."
  (:require [json.data-json :as json]
            [soukai.noticeport :as noticeport]
            [soukai.store :as store]
            [mail.message :as message]
            [mailer.core :as mailer]))

(defn- resend-api-key []
  (or (System/getenv "RESEND_API_KEY")
      (throw (ex-info "RESEND_API_KEY is not set" {}))))

(defn jvm-http-fn
  "Real java.net.http transport, same {:url :method :headers :body} ->
  {:status :body} convention as koyomi.distribute/jvm-http-fn —
  lets send-notice! be tested with a stubbed :http-fn instead of a real
  Resend call."
  []
  (fn [{:keys [url method headers body]}]
    (let [builder (-> (java.net.http.HttpRequest/newBuilder (java.net.URI/create url))
                      (as-> b (reduce-kv (fn [b k v] (.header b k v)) b headers)))
          request (case method
                    :post (-> builder
                             (.POST (java.net.http.HttpRequest$BodyPublishers/ofString (or body "")))
                             .build)
                    (throw (ex-info "Unsupported HTTP method" {:method method})))
          resp (.send (java.net.http.HttpClient/newHttpClient) request
                     (java.net.http.HttpResponse$BodyHandlers/ofString))]
      {:status (.statusCode resp) :body (.body resp)})))

(defn notice-message
  "Build the mail.message/message for a soukai :convocation/send notification.
  `from` is the verified Resend sender address — REQUIRED, no hardcoded
  default (same discipline as koyomi.distribute/share-message). `recipients`
  is the operator-supplied vector of real shareholder email addresses (see
  the namespace docstring's recipients-are-operator-supplied discussion —
  NOT derived from `content`). `text` is the ALREADY-BUILT `soukai.
  noticeport/notice-text` plain-text notice (computed once by the caller,
  same discipline as koyomi.distribute/share!'s single `ics-string` call
  threaded to both the message and the ledger record) — it becomes the
  message body directly, no attachment, unlike koyomi's ICS invite.
  `meeting-id` is the subject line's identifier: unlike koyomi's calendar
  content (which carries a :calendar/title), soukai's convocation content
  has no single title field (:agenda-titles is a vector), so the meeting id
  is the stable, human-checkable subject anchor instead."
  [from recipients meeting-id text]
  (message/message
   {:from from
    :to recipients
    :subject (str "株主総会招集通知: " meeting-id)
    :text text}))

(defn send-notice!
  "POST a soukai convocation-notice email (`m`, already built by
  `notice-message`) to Resend via `http-fn` (default jvm-http-fn, a real
  network call). Mirrors koyomi.distribute/send-invite! exactly, minus the
  ICS-attachment step (soukai has no separate calendar-invite artifact — see
  the namespace docstring), so the `mailer.core/request`-built `:http/json`
  envelope is posted as-is. Returns the parsed JSON response body. Throws on
  a non-2xx status or a missing RESEND_API_KEY (via `token`)."
  ([m] (send-notice! m {}))
  ([m {:keys [http-fn token] :or {http-fn (jvm-http-fn)}}]
   (let [request (mailer/request :resend {:mail.effect/type :mail/send :mail.effect/message m})
         resp (http-fn {:url (:http/url request)
                        :method :post
                        :headers {"Authorization" (str "Bearer " (or token (resend-api-key)))
                                  "Content-Type" "application/json"}
                        :body (json/write-str (:http/json request))})
         resp-body (json/read-str (:body resp) :key-fn keyword)]
     (when-not (< (:status resp) 300)
       (throw (ex-info "Resend send failed" {:status (:status resp) :body resp-body})))
     resp-body)))

(defn resend-noticeport
  "A REAL soukai.noticeport/NoticeTarget backed by Resend — the opt-in
   Distributor for :convocation/send (mock-noticeport stays the default).
   `recipients` is an operator-supplied vector of real shareholder email
   addresses (soukai's own data model keeps shareholder-id and email
   address deliberately separate -- see namespace docstring -- so unlike
   koyomi.distribute's reuse of :calendar/attendees as recipients, this
   constructor requires the caller to supply the actual mailing list, not
   something derived from the meeting's record-date snapshot).

   `store` should be the SAME `soukai.store/Store` the actor is built
   against: `send!` records the Resend message id onto that store's
   append-only ledger (the soukai analog of `koyomi.distribute`'s
   `:t :shared-externally` ledger fact, adapted to soukai's own `:t`
   vocabulary — see `soukai.operation`'s `:recorded`/`:committed`/
   `:human-signoff` facts) directly inside `send!`, since `soukai.
   operation`'s `commit-effects!` discards `send!`'s return value today.
   `from` is REQUIRED — see `notice-message`'s docstring.
   `fetch-convocation`/`propose-revision!` mirror `mock-noticeport`'s
   in-memory bookkeeping verbatim (control-plane only; no real backend for
   those)."
  [store recipients from & [{:keys [shared http-fn token]
                             :or {shared (atom {}) http-fn (jvm-http-fn)}}]]
  (reify noticeport/NoticeTarget
    (fetch-convocation [_ meeting-id] (get @shared meeting-id))
    (propose-revision! [_ meeting-id _content] {:proposal-id (str "soukai/" meeting-id)})
    (send! [_ meeting-id content]
      (let [text (noticeport/notice-text content)
            m (notice-message from recipients meeting-id text)
            resp (send-notice! m {:http-fn http-fn :token token})
            id (:id resp)
            rec {:meeting-id meeting-id :text text :recipients recipients :resend-id id}]
        (store/append-ledger! store {:t :sent-externally :op :convocation/send :subject meeting-id
                                     :disposition :sent :tool (str "resend:" id)})
        (swap! shared assoc meeting-id rec)
        rec))))
