(ns smtp.guest-document
  "Clojure data -> the tagged `:document` the KIR runtime hands a Kotoba
  guest, so a parity test can call an export that takes a message or a
  session state without hand-writing `[\"map\" [[[\"keyword\" :to] …]]]`.

  Only the shapes these guests read are covered: string, keyword, integer,
  vector, map. A nil VALUE is dropped rather than encoded, because that is
  what a document is — `smtp.protocol`'s `header-list` distinguishes an
  absent key from an empty string, and so do the guests.")

(defn ->doc
  "Encode `x`. Map keys must be keywords; nil values are dropped."
  [x]
  (cond
    (string? x) ["string" x]
    (keyword? x) ["keyword" x]
    (integer? x) ["i64" x]
    (boolean? x) ["bool" x]
    (map? x) ["map" (mapv (fn [[k v]] [["keyword" k] (->doc v)])
                          (sort-by key (remove (comp nil? val) x)))]
    (sequential? x) ["vector" (mapv ->doc x)]
    (nil? x) ["null" nil]
    :else (throw (ex-info "no document encoding" {:value x}))))

(defn strings
  "The inverse for the one shape a guest hands back here: a vector of strings."
  [d]
  (mapv second (second d)))
