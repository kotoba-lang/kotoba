(ns rtsp.session-header
  "The `Session` header — [RFC 2326] §12.37 — verbatim ABNF:

    Session = \"Session\" \":\" session-id [ \";\" \"timeout\" \"=\" delta-seconds ]

  and the RFC's own note that `timeout` \"is only allowed in a response
  header\" — a server tells a client how long it will hold the session
  without activity; a client never sends one back.")

(require '[kotoba.lang.text :as str])

(defn decode
  "`Session` header value -> `{:session-id \"...\" :timeout <seconds-or-nil>}`,
  or `[:error :rtsp/malformed-session-header]` if the timeout parameter
  is present but not `timeout=<digits>`."
  [value]
  (let [semi (str/index-of value \;)]
    (if (nil? semi)
      [:ok {:session-id value :timeout nil}]
      (let [id (subs value 0 semi)
            rest' (str/trim (subs value (inc semi)))]
        (if-let [[_ n] (re-matches #"timeout=(\d+)" rest')]
          [:ok {:session-id id :timeout (parse-long n)}]
          [:error :rtsp/malformed-session-header])))))

(defn encode [{:keys [session-id timeout]}]
  (str session-id (when timeout (str ";timeout=" timeout))))
