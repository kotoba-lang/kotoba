(ns gmail.history
  "Gmail incremental-sync history reads. REST v1, JVM-only.

  `users.history.list` returns everything that changed since a given
  `historyId` (message added/deleted, label added/removed) without
  re-scanning the whole mailbox. A caller persists the last-seen
  `historyId` (from any prior threads/messages response, or from
  `list-history`'s own `:historyId` field) and passes it back in as
  `start-history-id` on the next call -- this is what closes the gap
  `threads/list-threads` alone can't: polling by `q`/date has no cursor,
  so it can't tell \"new since last time\" from \"everything again\"."
  (:require [gmail.client :as client]))

#?(:clj
(defn list-history
  "List history records since `start-history-id`, paginated via
  `page-token` like gmail.threads/list-threads.

  Gmail's `historyTypes` filter is intentionally NOT exposed here: it's a
  repeated query param (`historyTypes=messageAdded&historyTypes=...`), and
  `gmail.client/request!`'s query-string builder only supports one value
  per key (see its `(map (fn [[k v]] (str (name k) \"=\" v)) query)`) --
  passing a vector through would silently serialize wrong. Filter the
  returned `:history` records client-side instead (each record's shape
  tells you which of messagesAdded/messagesDeleted/labelsAdded/
  labelsRemoved it is) until client.cljc grows real array-param support.

  Gmail returns 404 once `start-history-id` is too old (mailbox history
  is not retained forever) -- callers must treat that as \"cursor
  expired, do a full resync\", not retry."
  ([start-history-id] (list-history start-history-id {}))
  ([start-history-id {:keys [page-token] :as http-opts}]
   (client/request! "/history"
                    (assoc (dissoc http-opts :page-token)
                           :query (cond-> {:startHistoryId start-history-id}
                                    page-token (assoc :pageToken page-token)))))))
