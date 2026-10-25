(ns sigv4.request
  "Sign one S3-compatible request: config in, `{:url :headers}` out.

  `sigv4.core` is the string layer; this is the composition over it — payload
  hash, header set, canonical request, key ladder, `Authorization`. Every
  consumer in this workspace had written that composition itself, which is the
  larger half of what was duplicated: sharing only the string layer would have
  left the same twenty lines of orchestration in nine places, each free to get
  the header set or the payload hash subtly wrong.

  Endpoint-agnostic. Backblaze B2, Cloudflare R2, Storj Gateway-MT and Amazon
  S3 all speak the same protocol here; which endpoint is legitimate is the
  caller's policy, not this namespace's."
  (:require [kotoba.lang.text :as str]
            [sigv4.core :as v4]
            [sigv4.protocols :as p]))

(defn- then [v f]
  #?(:clj (f v) :cljs (.then (js/Promise.resolve v) f)))

(defn- host-of [endpoint]
  #?(:clj  (.getHost (java.net.URI. endpoint))
     :cljs (.-host (js/URL. endpoint))))

(defn signing-key
  "Fold the HMAC ladder. → the derived signing key (or a thenable of one).
  Exposed because presign flows and multi-request sessions reuse it."
  [crypto secret-key short-date region service]
  (let [{:keys [seed steps]} (v4/signing-key-chain secret-key short-date region service)]
    (reduce (fn [k step] (then k #(p/-hmac crypto % step))) seed steps)))

(defn signed
  "Sign an S3 request. → `{:method :url :headers :body}`, a Promise of it on
  ClojureScript.

      (signed crypto {:endpoint \"https://gateway.storjshare.io\"
                      :bucket \"b\" :region \"us-east-1\"
                      :access-key \"…\" :secret-key \"…\"
                      :method :get :key \"docs/a.txt\"
                      :now (.toISOString (js/Date.))})

  `:now` is an ISO-8601 instant the caller supplies — the library reads no
  clock, which is what makes a signature reproducible and therefore testable.
  `:payload-hash` defaults to the SHA-256 of `:body`, or the empty-string hash
  when there is no body; pass `sigv4.core/unsigned-payload` for a streaming
  body. `:headers` are merged in and signed, so anything you put there
  (`content-type`, `range`) is covered by the signature. `:service` defaults to
  `s3`."
  [crypto {:keys [endpoint bucket region service access-key secret-key
                  method key query headers body payload-hash now]
           :or   {service v4/default-service}}]
  (let [origin (str/replace (str endpoint) #"/+$" "")
        host   (host-of origin)
        {:keys [long short]} (v4/amz-dates now)
        path   (v4/object-path bucket key)
        qs     (v4/canonical-query query)
        scope  (v4/credential-scope short region service)]
    (then (or payload-hash
              (if (some? body) (p/-sha256-hex crypto body) v4/empty-payload-sha256))
          (fn [payload-hash]
            (let [headers (merge (into {} (map (fn [[k v]] [(str/lower (name k)) (str v)]))
                                       headers)
                                 {"host"                 host
                                  "x-amz-content-sha256" payload-hash
                                  "x-amz-date"           long})
                  {:keys [canonical-request signed-headers]}
                  (v4/canonical-request {:method       method
                                         :path         path
                                         :query        qs
                                         :headers      headers
                                         :payload-hash payload-hash})]
              (then (p/-sha256-hex crypto canonical-request)
                    (fn [cr-hash]
                      (let [sts (v4/string-to-sign long scope cr-hash)]
                        (then (signing-key crypto secret-key short region service)
                              (fn [k]
                                (then (p/-hmac crypto k sts)
                                      (fn [sig]
                                        {:method  (str/upper (name method))
                                         :url     (str origin path (when (seq qs) (str "?" qs)))
                                         :headers (assoc headers "authorization"
                                                         (v4/authorization-header
                                                          access-key scope signed-headers
                                                          (p/-hex crypto sig)))
                                         :body    body}))))))))))))

(defn presigned-request
  "Presigned URL, plus the headers a client MUST send with it.

  → `{:url :method :headers :signed-headers :expires-seconds}` (a Promise of
  it on JS). `presigned` is this without the envelope, for the common case.

  `host` is always signed, which is what lets the URL work from a browser.
  Anything in `:headers` is signed TOO, and that is the difference between a
  URL and a capability with a shape:

      (presigned-request c {… :method :put :headers {\"content-length\" \"12345\"}})

  Without it, a presigned PUT is a blank cheque — whoever holds the URL may
  store any number of bytes under a key whose content they never had to know.
  Listing a header in the request while signing only `host` binds nothing;
  the constraint has to be in the signature, and the returned `:headers` are
  exactly what the client has to send back for that signature to verify.

  `:expires-seconds` defaults to 3600 and is capped by S3 at 604800 (7 days)."
  [crypto {:keys [endpoint bucket region service access-key secret-key
                  method key query headers now expires-seconds]
           :or   {method :get expires-seconds 3600 service v4/default-service
                  ;; A presign without a timestamp signs an EMPTY X-Amz-Date,
                  ;; which every real S3 endpoint answers 403 AccessDenied to
                  ;; (measured live against B2 2026-09-05). The reference
                  ;; vectors pass :now explicitly; a production caller that
                  ;; forgot it used to fail only in production.
                  now #?(:cljs (.toISOString (js/Date.)) :clj (str (java.time.Instant/now)))}}]
  (let [origin (str/replace (str endpoint) #"/+$" "")
        host   (host-of origin)
        ;; `host` last: a caller cannot sign a host the URL does not point at.
        hs     (-> (into {} (map (fn [[k v]] [(str/lower (name k)) (str/trim (str v))]))
                         headers)
                   (assoc "host" host))
        {:keys [long short]} (v4/amz-dates now)
        scope  (v4/credential-scope short region service)
        path   (v4/object-path bucket key)
        canonical (fn [qs] (v4/canonical-request {:method       method
                                                  :path         path
                                                  :query        qs
                                                  :headers      hs
                                                  :payload-hash v4/unsigned-payload}))
        ;; X-Amz-SignedHeaders is a QUERY parameter, so the header list has to
        ;; exist before the canonical query does. Take it from the same
        ;; function that will build the canonical request rather than sorting
        ;; the keys again here — two orderings that must agree are two
        ;; orderings that can drift, and the symptom would be a 403 with no
        ;; local reproduction.
        signed (:signed-headers (canonical ""))
        qs     (v4/canonical-query
                (merge query
                       (v4/presign-params {:key-id          access-key
                                           :scope           scope
                                           :long-date       long
                                           :expires-seconds expires-seconds
                                           :signed-headers  signed})))
        {:keys [canonical-request]} (canonical qs)]
    (then (p/-sha256-hex crypto canonical-request)
          (fn [cr-hash]
            (let [sts (v4/string-to-sign long scope cr-hash)]
              (then (signing-key crypto secret-key short region service)
                    (fn [k]
                      (then (p/-hmac crypto k sts)
                            (fn [sig]
                              {:url (str origin path "?" qs
                                         "&X-Amz-Signature=" (p/-hex crypto sig))
                               :method method
                               ;; host is set by the HTTP client itself; a
                               ;; fetch() cannot set it and does not need to.
                               :headers (dissoc hs "host")
                               :signed-headers signed
                               :expires-seconds expires-seconds})))))))))

(defn presigned
  "Presigned URL — a bare `https://…?X-Amz-…` anyone can fetch until it expires,
  with no credentials on the wire. → a URL string (a Promise of one on JS).

  Only `host` is signed unless you pass `:headers`, in which case use
  `presigned-request` instead: it returns the headers the client must send,
  and a signed header the client does not know about is a URL that 403s."
  [crypto opts]
  ;; `(fn [r] (:url r))`, not the bare `:url` keyword. On the JVM `then`
  ;; applies f itself and a keyword works; on JS it becomes
  ;; `promise.then(kw)`, and a ClojureScript Keyword is an object rather than
  ;; `typeof "function"` — so the Promise spec IGNORES it and resolves with
  ;; the input unchanged. The JVM suite passed while cljs handed back the
  ;; whole map; `scripts/verify-cljs.cljs` is what caught it.
  (then (presigned-request crypto opts) (fn [r] (:url r))))
