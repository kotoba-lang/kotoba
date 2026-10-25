(ns kotobase.protocols.webdav
  "webdav.kotobase.net — a WebDAV (RFC 4918) surface projected onto the
  kotobase IStore document space (ADR-2607172210, KRP §16.1 — WebDAV
  maps onto the Name identity, §3.1, with an explicit collection-vs-
  resource flag since WebDAV has real folder semantics that flat
  S3-style keys don't).

  Mapping:
    share            → IStore collection [:kotobase.webdav/resources <share>]
                        (one collection per share, analogous to S3's bucket)
    path below share → doc key (may contain '/')
    doc value        → {:bytes :content-type :webdav/collection? bool
                        :last-modified}
    every write      → audit event on :kotobase.protocols/audit

  A share's root (\"/{share}\" or \"/{share}/\") is always an implicit
  collection — it needs no MKCOL and cannot be created or deleted.

  Implemented subset (v0.1, per ADR-2607172210):
    OPTIONS  /{share}[/{path}]     capability discovery (Allow, DAV headers)
    GET      /{share}/{path}       fetch resource body
    HEAD     /{share}/{path}       fetch resource metadata only
    PUT      /{share}/{path}       create/replace a resource (201/200)
    DELETE   /{share}/{path}       delete a resource, or a collection and
                                    everything under it (204)
    MKCOL    /{share}/{path}       create a collection (201)
    PROPFIND /{share}[/{path}]     Depth 0 or 1 only, minimal
                                    <D:multistatus> response — just
                                    <D:href>, <D:getcontentlength>,
                                    <D:getcontenttype>, and
                                    <D:resourcetype> (<D:collection/>
                                    when applicable). No other DAV
                                    property is reported.

  Deliberately out of scope here (ADR-2607172210 v0.1 boundary — same
  discipline as kotobase.protocols.s3's SigV4/multipart/versioning
  carve-out):
    - LOCK / UNLOCK (no lock tokens, no If: header enforcement — every
      write in this handler is unconditional).
    - COPY / MOVE.
    - PROPPATCH (no custom/dead property storage — PROPFIND always
      reports the same fixed live-property set above).
    - PROPFIND Depth: infinity (rejected with 403; only 0 and 1 are
      implemented).
    - Binary bodies — string body only (KRP addressing / http.cljc
      v0.1 constraint, an explicit, deliberate follow-up, not solved
      here).
    - Authentication (Basic/Digest/bearer) — the deploy shell owns
      auth, exactly as CACAO verification lives in the kotobase.net
      Worker, not in the engine."
  (:require [kotoba.lang.text :as str]
            [kotobase.protocols.http :as http]
            [kotobase.store :as st]))

(defn resources-coll [share] [:kotobase.webdav/resources share])

(defn- root? [k] (or (nil? k) (= k "")))

(defn- audit! [store op share k]
  (st/-append store :kotobase.protocols/audit
              {:surface :webdav :op op :share share :key k}))

(defn- collection?
  "True when `k` is a collection — the implicit share root always is;
  otherwise the stored doc's :webdav/collection? flag decides."
  [store share k]
  (if (root? k)
    true
    (boolean (:webdav/collection? (st/-get store (resources-coll share) k)))))

(defn- parent-key
  "The immediate parent key of `k`, or nil when `k`'s parent is the
  (always-present) share root."
  [k]
  (when (and k (str/includes? k "/"))
    (subs k 0 (str/last-index-of k "/"))))

(defn- parent-ok?
  "WebDAV MKCOL/PUT only require the *immediate* parent collection to
  already exist (mirrors filesystem mkdir/create semantics) — deeper
  ancestors are not re-checked."
  [store share k]
  (let [p (parent-key k)]
    (or (nil? p) (collection? store share p))))

(defn- get-doc
  "The stored doc at `k`, or a synthetic doc describing the always-
  present share root when `k` is root."
  [store share k]
  (if (root? k)
    {:webdav/collection? true :bytes "" :content-type nil :last-modified nil}
    (st/-get store (resources-coll share) k)))

(defn- href [share k]
  (str "/" share (when-not (root? k) (str "/" k))))

(defn- xml-response [status body]
  (http/response status {"content-type" "application/xml; charset=utf-8"}
                 (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" body)))

(defn- resource-xml [share k doc]
  (str "<D:response>"
       "<D:href>" (http/xml-escape (href share k)) "</D:href>"
       "<D:propstat><D:prop>"
       (if (:webdav/collection? doc)
         "<D:resourcetype><D:collection/></D:resourcetype>"
         (str "<D:resourcetype/>"
              "<D:getcontentlength>" (count (:bytes doc)) "</D:getcontentlength>"
              "<D:getcontenttype>"
              (http/xml-escape (or (:content-type doc) "application/octet-stream"))
              "</D:getcontenttype>"))
       "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
       "</D:response>"))

(defn- immediate-children
  "Keys directly below `k` (or below the share root when `k` is root),
  one segment deep. IStore -put never removes a key on delete — it
  writes a nil tombstone (see kotobase.protocols.s3's -list comment) —
  so tombstoned keys are filtered out via a live -get."
  [store share k]
  (let [prefix (if (root? k) "" (str k "/"))]
    (->> (st/-list store (resources-coll share))
         (filter #(str/starts-with? % prefix))
         (keep (fn [full]
                 (let [rel (subs full (count prefix))]
                   (when (and (seq rel) (not (str/includes? rel "/")))
                     full))))
         distinct
         (filter #(st/-get store (resources-coll share) %))
         sort)))

(defn- options-response []
  (http/response 200
                 {"allow" "OPTIONS, GET, HEAD, PUT, DELETE, PROPFIND, MKCOL"
                  "dav" "1"}
                 nil))

(defn- propfind [store share k depth-header]
  (let [doc (get-doc store share k)]
    (cond
      (nil? doc)
      (http/not-found (str "no such resource: " k))

      (= depth-header "infinity")
      (http/text 403 "Depth: infinity is not supported (v0.1)")

      :else
      (let [depth (or depth-header "0")
            self-xml (resource-xml share k doc)
            children-xml (when (and (= depth "1") (:webdav/collection? doc))
                           (apply str
                                  (for [ck (immediate-children store share k)]
                                    (resource-xml share ck
                                                  (st/-get store (resources-coll share) ck)))))]
        (xml-response 207
                      (str "<D:multistatus xmlns:D=\"DAV:\">"
                           self-xml children-xml
                           "</D:multistatus>"))))))

(defn- mkcol! [store share k now]
  (cond
    (root? k)
    (http/text 405 "MKCOL on the share root is not allowed")

    (st/-get store (resources-coll share) k)
    (http/text 405 (str "MKCOL target already exists: " k))

    (not (parent-ok? store share k))
    (http/text 409 (str "MKCOL parent collection does not exist: " (parent-key k)))

    :else
    (do (st/-put store (resources-coll share) k
                 {:bytes "" :content-type nil :webdav/collection? true :last-modified now})
        (audit! store :mkcol share k)
        (http/response 201 {} nil))))

(defn- put! [store share k req now]
  (cond
    (root? k)
    (http/text 405 "PUT on the share root is not allowed")

    (collection? store share k)
    (http/text 409 (str "PUT target is a collection: " k))

    (not (parent-ok? store share k))
    (http/text 409 (str "PUT parent collection does not exist: " (parent-key k)))

    :else
    (let [existing? (some? (st/-get store (resources-coll share) k))
          body (or (:body req) "")
          doc {:bytes body
               :content-type (or (http/header req "content-type") "application/octet-stream")
               :webdav/collection? false
               :last-modified now}]
      (st/-put store (resources-coll share) k doc)
      (audit! store :put share k)
      (http/response (if existing? 200 201) {} nil))))

(defn- get-or-head [store share k method]
  (let [doc (get-doc store share k)]
    (cond
      (nil? doc)
      (http/not-found (str "no such resource: " k))

      (:webdav/collection? doc)
      (http/response 200 {"content-type" "httpd/unix-directory"}
                     (when (= method :get) ""))

      :else
      (http/response 200
                     (cond-> {"content-type" (or (:content-type doc) "application/octet-stream")
                              "content-length" (str (count (:bytes doc)))}
                       (:last-modified doc) (assoc "last-modified" (:last-modified doc)))
                     (when (= method :get) (:bytes doc))))))

(defn- descendant-keys [store share k]
  (let [prefix (str k "/")]
    (->> (st/-list store (resources-coll share))
         (filter #(str/starts-with? % prefix)))))

(defn- delete! [store share k]
  (cond
    (root? k)
    (http/text 403 "DELETE of the share root is not allowed")

    (nil? (st/-get store (resources-coll share) k))
    (http/not-found (str "no such resource: " k))

    :else
    (let [doc (st/-get store (resources-coll share) k)]
      (if (:webdav/collection? doc)
        (do (doseq [ck (descendant-keys store share k)]
              (st/-put store (resources-coll share) ck nil))
            (st/-put store (resources-coll share) k nil)
            (audit! store :delete-collection share k)
            (http/response 204 {} nil))
        (do (st/-put store (resources-coll share) k nil)
            (audit! store :delete share k)
            (http/response 204 {} nil))))))

(defn handle
  "WebDAV surface handler. `ctx` is {:store IStore, :now optional ISO
  string}. `req` extends kotobase.protocols.http's shape with the
  WebDAV-specific methods :propfind and :mkcol (in addition to the
  base :get/:put/:post/:head/:delete, plus :options here)."
  [{:keys [store now]} req]
  (let [[share & ks] (http/segments (:path req))
        k (when (seq ks) (str/join "/" ks))]
    (if (nil? share)
      (http/text 400 "share missing")
      (case (:method req)
        :options (options-response)
        :propfind (propfind store share k (http/header req "depth"))
        :mkcol (mkcol! store share k now)
        :put (put! store share k req now)
        (:get :head) (get-or-head store share k (:method req))
        :delete (delete! store share k)
        (http/text 405 "unsupported WebDAV method")))))
