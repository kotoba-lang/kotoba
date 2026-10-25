(ns nostr.blossom
  "NIP-98 HTTP Auth + Blossom BUD-01/02 blob storage
  (ADR-2607172210's nostr.blossom, KRP §16.3: a Blossom blob's sha256 is
  Content identity, KRP §3.3 — a domain-specific content hash, not a CID).

  Storage: one IStore collection, :nostr.blossom/blobs, keyed by lowercase
  hex sha256, holding {:bytes :content-type :uploaded-at :uploaded-by}. This
  mirrors the {:bytes :content-type} shape
  kotobase-protocols/src/kotobase/protocols/blocks.cljc uses for its shared
  content-addressed block space (this repo does not depend on that repo —
  same shape for consistency, not code reuse), plus two Blossom-specific
  fields.

  SCOPE (v0.1, honest about what's real vs. simplified — same discipline as
  kotobase-protocols' own README):
    - PUT /upload does NOT require NIP-98 auth (matches many real Blossom
      servers' public-upload policy, and is what this repo's owning ADR
      literally specifies: only DELETE is called out as requiring auth).
      When an Authorization header IS present on upload, it's still
      verified and, if valid, its pubkey is recorded as :uploaded-by.
    - DELETE /<sha256> REQUIRES a valid NIP-98 auth event (kind 27235,
      method DELETE, u = this request's URL, fresh created_at). It does
      NOT additionally check that the deleting pubkey matches
      :uploaded-by (ownership enforcement) — any holder of a validly-signed,
      freshly-timestamped auth event for this exact URL can delete. This is
      a real, disclosed v0.1 gap (a production Blossom server should add
      ownership checks), not a silently-skipped requirement.
    - Bodies are strings (binary upload is a follow-up), same documented
      limitation nostr.http/kotobase-protocols' http.cljc carries.
    - GET is fully public, no auth, matching Blossom's read model."
  (:require [kotoba.lang.text :as str]
            [kotobase.store :as st]
            [nostr.crypto :as crypto]
            [nostr.event :as event]
            [nostr.http :as http]
            [nostr.json :as json]))

(def coll :nostr.blossom/blobs)

(defn- audit! [store op data]
  (st/-append store :nostr.blossom/audit (merge {:surface :blossom :op op} data)))

;; ------------------------------------------------------------------- base64

(defn base64-decode-to-str
  "base64 string -> UTF-8 decoded string. Throws on malformed input."
  [^String b64]
  #?(:clj (String. (.decode (java.util.Base64/getDecoder) b64) "UTF-8")
     :cljs (.toString (js/Buffer.from b64 "base64") "utf8")))

;; ----------------------------------------------------------------- NIP-98

(def nip98-kind 27235)
(def default-window-s 60)

(defn- extract-auth-event
  "Authorization header value -> parsed event map, or nil if the header is
  missing/malformed (not \"Nostr <base64>\", not valid base64, not valid
  JSON)."
  [header-val]
  (when (and header-val (str/starts-with? header-val "Nostr "))
    (try
      (json/parse (base64-decode-to-str (str/trim (subs header-val 6))))
      #?(:clj (catch Exception _ nil) :cljs (catch :default _ nil)))))

(defn verify-nip98-auth
  "req: {:method :headers :path ...}. `url`: the exact absolute URL this
  request must match against the auth event's \"u\" tag (callers build this
  from their own ctx :base-url + req :path — this namespace has no notion
  of scheme/host on its own). `now-s`: current epoch seconds. `window-s`:
  allowed created_at skew (default 60s each direction, matching NIP-98's
  own recommendation).

  Returns {:ok? bool :reason kw-or-nil :pubkey hex-or-nil}. REAL BIP-340
  verification via nostr.event/signature-valid? -> nostr.crypto/schnorr-verify
  — see nostr.crypto's docstring for the honest status of that (it IS real,
  checked against official BIP-340 test vectors)."
  [req url now-s & {:keys [window-s] :or {window-s default-window-s}}]
  (let [header-val (http/header req "authorization")
        ev (extract-auth-event header-val)]
    (cond
      (nil? header-val) {:ok? false :reason :missing-auth-header :pubkey nil}
      (nil? ev) {:ok? false :reason :malformed-auth-header :pubkey nil}
      (not (:valid? (event/validate ev))) {:ok? false :reason :invalid-auth-event :pubkey nil}
      (not= nip98-kind (get ev "kind")) {:ok? false :reason :wrong-kind :pubkey nil}
      (not= url (first (event/tag-values ev "u"))) {:ok? false :reason :url-mismatch :pubkey nil}
      (not= (str/upper (name (:method req)))
            (str/upper (or (first (event/tag-values ev "method")) "")))
      {:ok? false :reason :method-mismatch :pubkey nil}
      (> (abs (- now-s (get ev "created_at"))) window-s)
      {:ok? false :reason :expired :pubkey nil}
      :else {:ok? true :reason nil :pubkey (get ev "pubkey")})))

;; ------------------------------------------------------------------ upload

(defn- blob-descriptor [{:keys [base-url]} sha256 {:keys [content-type bytes uploaded-at]}]
  {"url" (str base-url "/" sha256)
   "sha256" sha256
   "size" (count bytes)
   "type" (or content-type "application/octet-stream")
   "uploaded" uploaded-at})

(defn- handle-put [{:keys [store now] :as ctx} req url]
  (let [body (or (:body req) "")
        sha256 (crypto/sha256-of-str body)
        content-type (or (http/header req "content-type") "application/octet-stream")
        header-val (http/header req "authorization")
        auth (when header-val (verify-nip98-auth req url now))
        blob {:bytes body :content-type content-type :uploaded-at now
              :uploaded-by (when (:ok? auth) (:pubkey auth))}]
    (if (and header-val (not (:ok? auth)))
      (http/unauthorized (str "invalid NIP-98 auth: " (name (:reason auth))))
      (do (st/-put store coll sha256 blob)
          (audit! store :put {:sha256 sha256 :size (count body) :uploaded-by (:uploaded-by blob)})
          (http/json-response 200 (blob-descriptor ctx sha256 blob) json/encode)))))

(defn- handle-get [{:keys [store]} sha256]
  (if-let [blob (st/-get store coll sha256)]
    (http/response 200 {"content-type" (:content-type blob)
                        "content-length" (str (count (:bytes blob)))}
                   (:bytes blob))
    (http/not-found (str "no such blob: " sha256))))

(defn- handle-delete [{:keys [store now]} req sha256 url]
  (let [auth (verify-nip98-auth req url now)]
    (cond
      (not (:ok? auth))
      (http/unauthorized (str "invalid NIP-98 auth: " (name (:reason auth))))

      (nil? (st/-get store coll sha256))
      (http/response 204 {} nil) ;; idempotent, matches s3.cljc's DELETE convention

      :else
      (do (st/-put store coll sha256 nil)
          (audit! store :delete {:sha256 sha256 :deleted-by (:pubkey auth)})
          (http/response 204 {} nil)))))

;; -------------------------------------------------------------------- route

(defn handle
  "Blossom surface handler. ctx: {:store IStore :now epoch-seconds-int
  :base-url \"https://blossom.example\"}. `url` used for NIP-98 \"u\" tag
  matching is (str base-url path) — exact string match, per NIP-98."
  [{:keys [base-url] :or {base-url ""} :as ctx} req]
  (let [path (or (:path req) "")
        url (str base-url path)]
    (cond
      (and (= :put (:method req)) (= path "/upload"))
      (handle-put ctx req url)

      (and (= :get (:method req)) (str/starts-with? path "/") (> (count path) 1))
      (handle-get ctx (subs path 1))

      (and (= :delete (:method req)) (str/starts-with? path "/") (> (count path) 1))
      (handle-delete ctx req (subs path 1) url)

      :else (http/not-found "no blossom route for this method/path"))))
