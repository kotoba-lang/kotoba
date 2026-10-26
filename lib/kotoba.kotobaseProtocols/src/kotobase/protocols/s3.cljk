(ns kotobase.protocols.s3
  "s3.kotobase.net — an S3-compatible object surface projected onto the
  kotobase IStore document space (ADR-2607171700, KRP §3.4 Location).

  Mapping:
    bucket        → IStore collection [:kotobase.s3/objects <bucket>]
    object key    → doc key (may contain '/')
    object value  → {:bytes :content-type :etag :last-modified}
    every write   → audit event on :kotobase.protocols/audit

  Implemented subset (v0.1):
    PUT    /{bucket}/{key}          store object
    GET    /{bucket}/{key}          fetch object
    HEAD   /{bucket}/{key}          metadata only
    DELETE /{bucket}/{key}          delete (idempotent 204)
    GET    /{bucket}?list-type=2    ListObjectsV2 (Key/ETag/Size, prefix=)

  Deliberately out of scope here: SigV4 authentication (the deploy
  shell owns auth, exactly as CACAO verification lives in the
  kotobase.net Worker, not in the engine), multipart upload,
  versioning. ETags are kotobase.protocols.hash fingerprints — a
  checksum, NOT a CID (KRP §3.3)."
  (:require [kotoba.lang.text :as str]
            [kotobase.protocols.hash :as hash]
            [kotobase.protocols.http :as http]
            [kotobase.store :as st]))

(defn objects-coll [bucket] [:kotobase.s3/objects bucket])

(defn- object-size
  "Byte length of an object, whichever era its record is from.

  An object value used to be REQUIRED to carry its body inline as
  `:bytes`. A deploy shell may now keep the bytes on a block plane and
  store `{:cid … :size …}` here instead — which is what
  s3.kotobase.net does, because bodies do not belong on the datom
  plane (superproject ADR-2608039970) and because the inline path was
  binary-unsafe.

  `:size` is therefore preferred and `(count (:bytes o))` is the
  fallback, never the other way round: for a record without inline
  bytes the fallback yields 0, and a listing that reports every object
  as empty is wrong in the one way nobody notices — it parses, it
  validates, and every size is a lie."
  [o]
  (or (:size o) (count (:bytes o)) 0))

(defn- audit! [store op bucket k]
  (st/-append store :kotobase.protocols/audit
              {:surface :s3 :op op :bucket bucket :key k}))

(defn- xml-response [status body]
  (http/response status {"content-type" "application/xml"}
                 (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" body)))

(defn- error-xml [status code msg]
  (xml-response status
                (str "<Error><Code>" code "</Code><Message>"
                     (http/xml-escape msg) "</Message></Error>")))

(def default-max-keys
  "S3's own default, and the value a client assumes when it sends none.

  Not a tuning knob: a listing with no ceiling is a response whose size is
  set by the bucket, and this one runs inside a Worker with a CPU limit. The
  surface used to return every key on every call, which worked until a
  bucket grew — and the failure it grows into is a timeout on the listing,
  i.e. the operation a client uses to find out what is there."
  1000)

(def max-max-keys
  "The ceiling on what a client can ask for in one page, as S3 defines it."
  1000)

(defn- parse-max-keys [v]
  (let [n (when (and (string? v) (re-matches #"\d{1,7}" (str/trim v)))
            #?(:clj (Long/parseLong (str/trim v))
               :cljs (js/parseInt (str/trim v) 10)))]
    (cond
      (nil? n) default-max-keys
      (zero? n) 0
      :else (min n max-max-keys))))

(defn- common-prefix
  "The `delimiter`-terminated prefix `k` falls under, or nil.

  This is what makes a flat key space look like directories: with
  `delimiter=/`, `a/b/c` collapses to `a/` and is reported ONCE as a
  CommonPrefix rather than as an object. rclone and every file-browser
  client depend on it — without it, listing a bucket at the top level
  returns every key in every directory, which is both wrong-looking and
  unbounded."
  [k prefix delimiter]
  (when (and delimiter (seq delimiter))
    (let [rest-of (subs k (count (or prefix "")))
          idx (str/index-of rest-of delimiter)]
      (when idx
        (str (or prefix "") (subs rest-of 0 (+ idx (count delimiter))))))))

(defn list-objects-page
  "One page of a bucket listing, as data.

  Separated from the XML so the paging decisions can be tested without
  parsing a document: which keys are in this page, whether there is another
  one, and what token the client must send to get it.

  The token is simply the last key of the page — S3's own
  ContinuationToken is opaque, and an opaque token here would mean either
  server-side cursor state (which nothing would ever clean up) or an
  encoding that pretends to be opaque while being a key in base64. It is
  documented as a key so nobody later depends on it being anything else."
  [all-keys get-fn {:keys [prefix delimiter max-keys start-after]}]
  (let [prefix (or prefix "")
        limit (if (nil? max-keys) default-max-keys max-keys)
        candidates (->> all-keys
                        (filter #(str/starts-with? % prefix))
                        sort
                        (drop-while #(and start-after (<= (compare % start-after) 0))))
        ;; One pass that stops as soon as the page is full, rather than
        ;; realising every key and taking the first N: the whole point is
        ;; that a big bucket costs a page, not a bucket.
        step (fn [{:keys [keys prefixes seen] :as acc} k]
               (if (>= (+ (count keys) (count prefixes)) limit)
                 (reduced (assoc acc :truncated? true :next-token (:last acc)))
                 (if-let [cp (common-prefix k prefix delimiter)]
                   (if (contains? seen cp)
                     (assoc acc :last k)
                     (-> acc (update :prefixes conj cp) (update :seen conj cp)
                         (assoc :last k)))
                   (if-let [o (get-fn k)]
                     (-> acc (update :keys conj [k o]) (assoc :last k))
                     ;; DELETE writes a nil tombstone (IStore docs have no
                     ;; remove op), so a key with no document is a deleted
                     ;; object and not a listing entry.
                     acc))))
        acc (reduce step {:keys [] :prefixes [] :seen #{} :last nil
                          :truncated? false :next-token nil}
                    candidates)]
    (select-keys acc [:keys :prefixes :truncated? :next-token])))

(defn- list-objects [store bucket {:keys [prefix delimiter max-keys start-after]}]
  (let [{:keys [keys prefixes truncated? next-token]}
        (list-objects-page (st/-list store (objects-coll bucket))
                           #(st/-get store (objects-coll bucket) %)
                           {:prefix prefix :delimiter delimiter
                            :max-keys max-keys :start-after start-after})]
    (xml-response
     200
     (str "<ListBucketResult>"
          "<Name>" (http/xml-escape bucket) "</Name>"
          "<Prefix>" (http/xml-escape (or prefix "")) "</Prefix>"
          (when (seq delimiter)
            (str "<Delimiter>" (http/xml-escape delimiter) "</Delimiter>"))
          "<MaxKeys>" (if (nil? max-keys) default-max-keys max-keys) "</MaxKeys>"
          "<KeyCount>" (+ (count keys) (count prefixes)) "</KeyCount>"
          "<IsTruncated>" (if truncated? "true" "false") "</IsTruncated>"
          (when truncated?
            (str "<NextContinuationToken>" (http/xml-escape next-token)
                 "</NextContinuationToken>"))
          (apply str
                 (for [[k o] keys]
                   (str "<Contents>"
                        "<Key>" (http/xml-escape k) "</Key>"
                        "<ETag>&quot;" (:etag o) "&quot;</ETag>"
                        "<Size>" (object-size o) "</Size>"
                        (when (:last-modified o)
                          (str "<LastModified>" (http/xml-escape (:last-modified o))
                               "</LastModified>"))
                        "<StorageClass>STANDARD</StorageClass>"
                        "</Contents>")))
          (apply str
                 (for [p prefixes]
                   (str "<CommonPrefixes><Prefix>" (http/xml-escape p)
                        "</Prefix></CommonPrefixes>")))
          "</ListBucketResult>"))))

(defn http-date
  "An ISO-8601 instant as the HTTP-date RFC 9110 requires.

  `<LastModified>` in a listing is ISO-8601, and the `last-modified` HEADER
  is not: HTTP carries `Tue, 18 Aug 2026 09:51:33 GMT`. Sending the listing
  format in the header is the kind of wrong most clients ignore and one does
  not — measured 2026-08-18 against the deployed surface, rclone tried every
  HTTP-date layout against `2026-08-18T09:51:33.156Z`, failed all of them,
  and abandoned the download, while the AWS CLI never looked.

  nil for a value it cannot parse, so an unparseable timestamp omits the
  header rather than emitting a second wrong format."
  [iso]
  (when (string? iso)
    #?(:clj
       (try (->> (-> (java.time.Instant/parse iso)
                     (.atZone java.time.ZoneOffset/UTC))
                 (.format java.time.format.DateTimeFormatter/RFC_1123_DATE_TIME))
            (catch Exception _ nil))
       :cljs
       (let [d (js/Date. iso)]
         (when-not (js/isNaN (.getTime d))
           (.toUTCString d))))))

(defn- object-headers [o]
  (cond-> {"content-type" (:content-type o)
           "etag" (str "\"" (:etag o) "\"")
           "content-length" (str (object-size o))}
    (http-date (:last-modified o))
    (assoc "last-modified" (http-date (:last-modified o)))))

(defn handle
  "S3 surface handler. `ctx` is {:store IStore, :now optional ISO string}."
  [{:keys [store now]} req]
  (let [[bucket & ks] (http/segments (:path req))
        k (when (seq ks) (str/join "/" ks))]
    (cond
      (nil? bucket)
      (error-xml 400 "InvalidRequest" "bucket missing")

      ;; bucket-level: ListObjectsV2
      (nil? k)
      (if (= :get (:method req))
        (list-objects store bucket
                      {:prefix (http/query-param req "prefix")
                       :delimiter (http/query-param req "delimiter")
                       :max-keys (parse-max-keys (http/query-param req "max-keys"))
                       ;; `continuation-token` and `start-after` are the same
                       ;; thing to this implementation — the token IS a key —
                       ;; and a client sends one or the other, never both in
                       ;; a way that disagrees.
                       :start-after (or (http/query-param req "continuation-token")
                                        (http/query-param req "start-after"))})
        (error-xml 405 "MethodNotAllowed" "unsupported bucket operation"))

      :else
      (case (:method req)
        :put
        (let [body (or (:body req) "")
              o {:bytes body
                 :content-type (or (http/header req "content-type")
                                   "application/octet-stream")
                 :etag (hash/fingerprint body)
                 :last-modified now}]
          (st/-put store (objects-coll bucket) k o)
          (audit! store :put-object bucket k)
          (http/response 200 {"etag" (str "\"" (:etag o) "\"")} nil))

        (:get :head)
        (if-let [o (st/-get store (objects-coll bucket) k)]
          (if (and (= :get (:method req)) (nil? (:bytes o)) (:cid o))
            ;; A record whose bytes live on a block plane. HEAD is still
            ;; answerable from metadata alone, but GET is not: this
            ;; handler has no way to reach the block, and answering 200
            ;; with the right `content-length` and an empty body is the
            ;; worst available outcome — every client would read it as a
            ;; truncated object rather than as a surface that cannot
            ;; serve it. The deploy shell intercepts GET for these; if
            ;; one reaches here, the deployment is misconfigured and
            ;; should say so.
            (error-xml 501 "NotImplemented"
                       (str "object bytes are stored off this plane; "
                            "the deploy shell serves them"))
            (http/response 200 (object-headers o)
                           (when (= :get (:method req)) (:bytes o))))
          (error-xml 404 "NoSuchKey" (str "no such key: " k)))

        :delete
        (do (st/-put store (objects-coll bucket) k nil)
            (audit! store :delete-object bucket k)
            (http/response 204 {} nil))

        (error-xml 405 "MethodNotAllowed" "unsupported object operation")))))
