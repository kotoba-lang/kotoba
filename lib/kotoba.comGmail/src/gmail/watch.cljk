(ns gmail.watch
  "Gmail push-notification lifecycle: users.watch / users.stop. REST v1,
  JVM-only.

  `watch!` registers a Cloud Pub/Sub topic that Gmail publishes to whenever
  the mailbox changes; `stop!` cancels all push notifications. A watch lasts
  only ~7 days and MUST be renewed before its `:expiration` (a Unix-ms
  timestamp string in the response) or notifications silently stop arriving --
  callers re-issue `watch!` on a timer well before that deadline.

  OUT OF SCOPE -- caller-side GCP infrastructure, mirroring exactly how OAuth2
  token acquisition is out of scope for gmail.client. This namespace ONLY
  makes the two Gmail-side API calls. It does NOT:
    1. provision the Cloud Pub/Sub topic (`projects/<p>/topics/<t>`),
    2. grant the Gmail push service account
       gmail-api-push@system.gserviceaccount.com the Pub/Sub Publisher role
       on that topic (without which Gmail's watch call fails to publish), or
    3. run the webhook / push subscriber that receives the notifications.
  All three are prerequisites the caller sets up in GCP; `watch!` assumes the
  topic already exists and is publishable-to. The notification payload itself
  only carries the mailbox `historyId` -- the actual changes are then read
  with gmail.history/list-history, which is why `watch!` returns a starting
  `:historyId` to seed that cursor."
  (:require [gmail.client :as client]))

#?(:clj
(defn watch!
  "Start push notifications for the mailbox (Gmail's users.watch, POST
  /watch). `topic-name` is the fully-qualified Pub/Sub topic
  \"projects/<gcp-project>/topics/<topic>\" -- the caller provisions and
  grants publish rights on it (see the ns docstring's out-of-scope note).

  `opts` (besides the usual :http-fn/:token) accepts :label-ids -- an
  optional collection of Gmail label ids restricting WHICH label changes
  trigger a notification (e.g. only INBOX); omit it to watch the whole
  mailbox. Returns `{:historyId ... :expiration ...}`: persist :historyId
  as the starting cursor for gmail.history/list-history, and :expiration
  (Unix ms, ~7 days out) as the renew-by deadline."
  ([topic-name] (watch! topic-name {}))
  ([topic-name {:keys [label-ids] :as http-opts}]
   (client/request! "/watch"
                    (assoc (dissoc http-opts :label-ids)
                           :method :post
                           :body (cond-> {:topicName topic-name}
                                   (seq label-ids) (assoc :labelIds label-ids)))))))

#?(:clj
(defn stop!
  "Stop ALL push notifications for the mailbox (Gmail's users.stop, POST
  /stop, no body). Returns nil -- Gmail replies with an empty success body,
  which client/request! surfaces as nil rather than a JSON parse target.
  Cancels every active watch for the user (there is at most one), so this is
  the clean teardown counterpart to watch!; calling it when nothing is
  watched is a harmless success."
  ([] (stop! {}))
  ([http-opts]
   (client/request! "/stop" (assoc http-opts :method :post)))))
