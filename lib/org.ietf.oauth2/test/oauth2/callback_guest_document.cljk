(ns oauth2.callback-guest-document
  "Clojure data -> the tagged `:document` the KIR runtime hands a Kotoba
  guest, so a parity test can call an export that takes a config or a
  parsed query without hand-writing the tagged vectors.

  The same helper the other guests in this workspace carry. It is test
  scaffolding for a runtime encoding, not a second implementation of
  anything -- there is no product semantics here to drift.")

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
