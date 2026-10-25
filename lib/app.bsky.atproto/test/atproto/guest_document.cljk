(ns atproto.guest-document
  "Clojure data <-> the tagged `:document` the KIR runtime hands a Kotoba guest.

  `org-ietf-smtp`'s `smtp.guest-document` has the encoder; this adds the
  DECODER, because the profile shapes here are documents on BOTH sides and the
  parity assertion is a map against a map. Without it the comparison would have
  to be written against the tagged form, which is the shape of the runtime rather
  than the shape of the protocol -- and a test written against the runtime's shape
  stops noticing when the protocol's changes.

  Only the shapes these guests use are covered: string, keyword, i64, bool,
  vector, map, null. A nil VALUE is dropped rather than encoded, because that is
  what a document is: `profile-record` distinguishes an absent key from an empty
  string, and so does the oracle.")

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

(defn doc->
  "Decode a tagged document back to Clojure data. The inverse of `->doc` for
  every shape it produces; an unknown tag throws rather than returning something
  that would compare equal to nothing."
  [d]
  (let [[tag v] d]
    (case tag
      "string" v
      "keyword" v
      "i64" v
      "bool" v
      "null" nil
      "vector" (mapv doc-> v)
      "map" (into {} (map (fn [[k val]] [(doc-> k) (doc-> val)])) v)
      (throw (ex-info "no document decoding" {:tag tag :document d})))))
