(ns pop3.guest-document
  "Clojure data -> the tagged `:document` the KIR runtime hands a Kotoba
  guest, so a parity test can call an export that takes a config or a
  session state without hand-writing `[\"map\" [[[\"keyword\" :user] …]]]`.

  Only the shapes this guest reads are covered: string, keyword, integer,
  boolean, vector, map. A nil VALUE is dropped rather than encoded, because
  that is what a document is: `pop3.session` distinguishes an absent key
  from an empty string, and so does `init`.

  Copied from `org-ietf-smtp/test/smtp/guest_document.clj`, which is the
  same helper for the same runtime. It is test scaffolding, not a second
  implementation of anything -- there is no product semantics here to
  drift.")

(defn ->doc
  "Encode `x`. Map keys must be keywords; nil values are dropped."
  [x]
  (cond
    (string? x) ["string" x]
    (keyword? x) ["keyword" x]
    (boolean? x) ["bool" x]
    (integer? x) ["i64" x]
    (map? x) ["map" (mapv (fn [[k v]] [["keyword" k] (->doc v)])
                          (sort-by key (remove (comp nil? val) x)))]
    (sequential? x) ["vector" (mapv ->doc x)]
    (nil? x) ["null" nil]
    :else (throw (ex-info "no document encoding" {:value x}))))
