(ns gmail.threads
  "Gmail thread listing/reading/label-modification. REST v1, JVM-only."
  (:require [gmail.client :as client]))

#?(:clj
(defn list-threads
  "List threads, optionally filtered by `q` (Gmail search syntax, e.g.
  \"from:wise.com in:inbox\"), paginated via `max-results`/`page-token`."
  ([] (list-threads {}))
  ([{:keys [q max-results page-token] :as http-opts}]
   (client/request! "/threads"
                    (assoc (dissoc http-opts :q :max-results :page-token)
                           :query (cond-> {}
                                    q (assoc :q q)
                                    max-results (assoc :maxResults max-results)
                                    page-token (assoc :pageToken page-token)))))))

#?(:clj
(defn get-thread
  ([thread-id] (get-thread thread-id {}))
  ([thread-id http-opts]
   (client/request! (str "/threads/" thread-id) http-opts))))

#?(:clj
(defn modify-thread!
  "Add/remove label IDs on every message in a thread (and future messages
  added to it). `add-label-ids`/`remove-label-ids` are Gmail label IDs, not
  display names -- see gmail.labels/find-or-create-label! to resolve one."
  ([thread-id mods] (modify-thread! thread-id mods {}))
  ([thread-id {:keys [add-label-ids remove-label-ids]} http-opts]
   (client/request! (str "/threads/" thread-id "/modify")
                    (assoc http-opts
                           :method :post
                           :body (cond-> {}
                                   (seq add-label-ids) (assoc :addLabelIds add-label-ids)
                                   (seq remove-label-ids) (assoc :removeLabelIds remove-label-ids)))))))

#?(:clj
(defn archive-thread!
  "Remove the INBOX label -- Gmail's definition of archiving a thread."
  ([thread-id] (archive-thread! thread-id {}))
  ([thread-id http-opts]
   (modify-thread! thread-id {:remove-label-ids ["INBOX"]} http-opts))))

#?(:clj
(defn trash-thread!
  "Move every message in a thread to Trash (Gmail's threads.trash, POST
  /threads/{id}/trash). REVERSIBLE -- Trash retains the thread (~30 days by
  Gmail's policy) and untrash-thread! restores it. This is deliberately
  distinct from delete-thread!, which is permanent: reach for this one
  unless you truly mean to bypass Trash."
  ([thread-id] (trash-thread! thread-id {}))
  ([thread-id http-opts]
   (client/request! (str "/threads/" thread-id "/trash") (assoc http-opts :method :post)))))

#?(:clj
(defn untrash-thread!
  "Restore a thread from Trash (Gmail's threads.untrash, POST
  /threads/{id}/untrash) -- the inverse of trash-thread!. Exposed alongside
  trash-thread! on purpose: a trash without an untrash is a trap, leaving a
  caller that trashed a thread with no programmatic way to pull it back
  short of the Gmail UI."
  ([thread-id] (untrash-thread! thread-id {}))
  ([thread-id http-opts]
   (client/request! (str "/threads/" thread-id "/untrash") (assoc http-opts :method :post)))))

#?(:clj
(defn delete-thread!
  "PERMANENTLY delete a thread and all its messages (Gmail's threads.delete,
  DELETE /threads/{id}). PERMANENT -- bypasses Trash entirely, Gmail does
  not support undoing this. Most callers want trash-thread! instead (which
  is reversible). Also note this needs the broad https://mail.google.com/
  scope; the narrower gmail.modify scope can trash but not delete."
  ([thread-id] (delete-thread! thread-id {}))
  ([thread-id http-opts]
   (client/request! (str "/threads/" thread-id) (assoc http-opts :method :delete)))))
