(ns kotobase.protocols.oci
  "oci.kotobase.net — an OCI Distribution Spec v1.1 server projected onto
  the kotobase IStore document space (ADR-2607172210, KRP §16.2 /
  90-docs/adr/2607172200 — OCI tag → Name-like mutable pointer, OCI
  digest → Content identity, a real CID-shaped hash unlike ETags).

  ORAS NOTE (read this before building a second implementation): ORAS
  is NOT a separate wire protocol. ORAS's client is a convention over
  this exact same OCI Distribution Spec v1.1 API (manifests + blobs +
  the Referrers API) for distributing arbitrary artifacts instead of
  container images — same endpoints, same digest/tag identity, no
  separate mapping. This handler is the one server that satisfies both
  OCI and ORAS clients. Do not build a second 'oras' handler/repo;
  confirmed and documented in ADR-2607172210's Context/Rejected
  sections.

  Mapping:
    <name>          → may contain '/' (e.g. \"org/app\"); scopes both
                      collections below, matching the Docker/OCI
                      repository-name convention.
    manifests coll  → IStore collection [:kotobase.oci/manifests <name>],
                      keyed by *reference* (tag OR digest string).
                      A tag PUT is additionally indexed under its
                      computed digest, so a manifest pushed by tag is
                      always also retrievable by digest — matching real
                      registry behavior and the OCI conformance
                      expectation that every manifest has a canonical
                      digest address regardless of how it was pushed.
    blobs coll      → IStore collection [:kotobase.oci/blobs <name>],
                      keyed by digest only (blobs have no mutable name).
    tags/list       → derived, not stored: every manifests-coll key
                      that is NOT digest-shaped (kotobase.protocols.oci.digest/digest-shaped?).
    every write     → audit event on :kotobase.protocols/audit.

  Implemented subset (v0.1, per github.com/opencontainers/distribution-spec):
    GET  /v2/                                   ping/version check, 200 empty body
    GET  /v2/<name>/manifests/<reference>        fetch manifest by tag or digest
    HEAD /v2/<name>/manifests/<reference>        same, headers only
    PUT  /v2/<name>/manifests/<reference>        store manifest; digest computed + validated
    GET  /v2/<name>/blobs/<digest>                fetch blob by digest
    HEAD /v2/<name>/blobs/<digest>                same, headers only
    POST /v2/<name>/blobs/uploads/?digest=<d>     MONOLITHIC upload only (full body,
                                                   one request); digest validated
    GET  /v2/<name>/tags/list                     list known tags (not digests) for <name>

  Deliberately out of scope here:
  - **Chunked upload session flow** (POST to start a session + PATCH
    chunks + PUT to finalize). Only the monolithic single-POST-with-
    ?digest= upload is implemented. This mirrors s3.cljc's explicit
    multipart-upload carve-out — a real deploy shell that needs
    resumable/streamed pushes is a documented follow-up, not silently
    unsupported.
  - **Bearer-token verification.** `unauthorized` below emits the
    real WWW-Authenticate: Bearer realm=\"...\",service=\"...\",
    scope=\"...\" challenge shape on PUT manifest / POST blob upload
    when no `Authorization` header is present at all, but this
    namespace never validates a token's signature or claims — the
    deploy shell (Cloudflare Worker, browser worker, fleet peer) owns
    real bearer-token issuance/verification, exactly as SigV4
    verification is deferred by s3.cljc. Any non-empty Authorization
    header is currently accepted as \"the shell already checked this\".
  - **Binary blob bodies.** kotobase.protocols.http's :body is a
    string in v0.1 (its own documented follow-up); this handler hashes
    and stores that string as-is. Real deployments will often push
    binary-shaped OCI layers — base64/binary-body handling is a
    follow-up in http.cljc, not reinvented here.
  - **Referrers API** (`GET /v2/<name>/referrers/<digest>`) and content
    discovery extensions ORAS clients sometimes use beyond plain
    manifest/blob push+pull. Not required for the v0.1 push/pull round
    trip; a documented follow-up once a concrete ORAS consumer needs it.
  - **Manifest content validation** (schemaVersion, mediaType-specific
    layer/config referential integrity, garbage collection of
    unreferenced blobs). This handler stores and digest-validates
    opaque manifest bytes; it does not parse or interpret OCI manifest
    JSON structure."
  (:require [kotoba.lang.text :as str]
            [kotobase.protocols.http :as http]
            [kotobase.protocols.oci.digest :as digest]
            [kotobase.store :as st]))

;; --------------------------------------------------------------- storage

(defn manifests-coll [name] [:kotobase.oci/manifests name])
(defn blobs-coll [name] [:kotobase.oci/blobs name])

(defn- audit! [store op name ref]
  (st/-append store :kotobase.protocols/audit
              {:surface :oci :op op :name name :ref ref}))

;; ------------------------------------------------------------- json out
;; Hand-rolled, same discipline as s3.cljc's hand-rolled XML — this
;; handler never needs to *parse* JSON (manifest bytes are stored
;; opaque), only to emit small fixed-shape error/listing bodies.

(defn- json-esc [s]
  (-> (str s)
      (str/replace "\\" "\\\\")
      (str/replace "\"" "\\\"")
      (str/replace "\n" "\\n")))

(defn- error-json [code message]
  (str "{\"errors\":[{\"code\":\"" (json-esc code)
       "\",\"message\":\"" (json-esc message) "\"}]}"))

(defn- tags-json [name tags]
  (str "{\"name\":\"" (json-esc name) "\",\"tags\":["
       (str/join "," (map #(str "\"" (json-esc %) "\"") tags))
       "]}"))

(defn- json-error [status code message]
  (http/response status {"content-type" "application/json"} (error-json code message)))

(defn- name-unknown [name] (json-error 404 "NAME_UNKNOWN" (str "repository name not known: " name)))
(defn- manifest-unknown [name reference]
  (json-error 404 "MANIFEST_UNKNOWN" (str "manifest unknown: " name "@" reference)))
(defn- blob-unknown [name d]
  (json-error 404 "BLOB_UNKNOWN" (str "blob unknown: " name "@" d)))
(defn- digest-invalid [expected actual]
  (json-error 400 "DIGEST_INVALID"
              (str "provided digest " expected " does not match computed digest " actual)))

;; ----------------------------------------------------------- auth challenge

(defn- bearer-challenge
  "WWW-Authenticate: Bearer realm=\"...\",service=\"...\",scope=\"...\"
  shape only — no verification lives here, see namespace docstring."
  [{:keys [apex] :or {apex "kotobase.net"} :as ctx} name action]
  (let [realm (or (:oci/realm ctx) (str "https://auth." apex "/token"))
        service (or (:oci/service ctx) apex)]
    (str "Bearer realm=\"" realm "\",service=\"" service
         "\",scope=\"repository:" name ":" action "\"")))

(defn- authorized?
  "Presence check only: any non-empty Authorization header is treated
  as already-verified by the deploy shell. Never inspects the token."
  [req]
  (let [h (http/header req "authorization")]
    (boolean (and h (seq h)))))

(defn- unauthorized [ctx name action]
  (http/response 401
                 {"www-authenticate" (bearer-challenge ctx name action)
                  "content-type" "application/json"}
                 (error-json "UNAUTHORIZED" "authentication required")))

;; ---------------------------------------------------------------- ping

(defn- ping []
  (http/response 200 {"docker-distribution-api-version" "registry/2.0"} ""))

;; ------------------------------------------------------------ manifests

(defn- put-manifest [ctx req name reference]
  (if-not (authorized? req)
    (unauthorized ctx name "pull,push")
    (let [store (:store ctx)
          body (or (:body req) "")
          content-type (or (http/header req "content-type")
                            "application/vnd.oci.image.manifest.v1+json")
          d (digest/digest-of body)]
      (if (and (digest/digest-shaped? reference) (not= reference d))
        (digest-invalid reference d)
        (let [value {:bytes body :content-type content-type :digest d}]
          (st/-put store (manifests-coll name) reference value)
          ;; Always index by digest too, so a tag push is retrievable
          ;; by digest exactly like a real registry (see ns docstring).
          (when-not (= reference d)
            (st/-put store (manifests-coll name) d value))
          (audit! store :put-manifest name reference)
          (http/response 201
                         {"docker-content-digest" d
                          "content-type" content-type
                          "location" (str "/v2/" name "/manifests/" d)}
                         nil))))))

(defn- get-manifest [req name reference store]
  (if-let [v (st/-get store (manifests-coll name) reference)]
    (http/response 200
                   {"docker-content-digest" (:digest v)
                    "content-type" (:content-type v)
                    "content-length" (str (count (:bytes v)))}
                   (when (= :get (:method req)) (:bytes v)))
    (manifest-unknown name reference)))

;; ---------------------------------------------------------------- blobs

(defn- upload-blob [ctx req name]
  (if-not (authorized? req)
    (unauthorized ctx name "pull,push")
    (let [store (:store ctx)
          body (or (:body req) "")
          provided (http/query-param req "digest")
          d (digest/digest-of body)]
      (cond
        (nil? provided)
        (json-error 400 "DIGEST_INVALID"
                    "digest query parameter required for monolithic upload")

        (not= provided d)
        (digest-invalid provided d)

        :else
        (do
          (st/-put store (blobs-coll name) d {:bytes body})
          (audit! store :put-blob name d)
          (http/response 201
                         {"docker-content-digest" d
                          "location" (str "/v2/" name "/blobs/" d)}
                         nil))))))

(defn- get-blob [req name d store]
  (if-let [v (st/-get store (blobs-coll name) d)]
    (http/response 200
                   {"docker-content-digest" d
                    "content-type" "application/octet-stream"
                    "content-length" (str (count (:bytes v)))}
                   (when (= :get (:method req)) (:bytes v)))
    (blob-unknown name d)))

;; --------------------------------------------------------------- tags/list

(defn- tags-list [store name]
  (let [ks (st/-list store (manifests-coll name))]
    (if (empty? ks)
      (name-unknown name)
      (let [tags (->> ks (remove digest/digest-shaped?) sort)]
        (http/response 200 {"content-type" "application/json"} (tags-json name tags))))))

;; ------------------------------------------------------------------ router

(defn- name-of
  "Join every segment before the trailing `tail-count` route segments
  with '/', so repository names with '/' (e.g. \"org/app\") work."
  [rest tail-count]
  (str/join "/" (subvec rest 0 (- (count rest) tail-count))))

(defn handle
  "OCI Distribution Spec v2 handler. `ctx` is {:store IStore, :apex
  optional-string, :oci/realm optional-string, :oci/service
  optional-string}."
  [ctx req]
  (let [segs (http/segments (:path req))
        store (:store ctx)]
    (if (not= "v2" (first segs))
      (http/not-found "not an OCI Distribution Spec v2 path")
      (let [rest (subvec segs 1)
            n (count rest)]
        (cond
          (empty? rest)
          (if (= :get (:method req)) (ping) (http/method-not-allowed))

          (and (>= n 3) (= "manifests" (rest (- n 2))))
          (let [name (name-of rest 2) reference (peek rest)]
            (case (:method req)
              :put (put-manifest ctx req name reference)
              (:get :head) (get-manifest req name reference store)
              (http/method-not-allowed)))

          (and (>= n 3) (= ["blobs" "uploads"] (subvec rest (- n 2))))
          (let [name (name-of rest 2)]
            (if (= :post (:method req))
              (upload-blob ctx req name)
              (http/method-not-allowed)))

          (and (>= n 3) (= "blobs" (rest (- n 2))))
          (let [name (name-of rest 2) d (peek rest)]
            (case (:method req)
              (:get :head) (get-blob req name d store)
              (http/method-not-allowed)))

          (and (>= n 3) (= ["tags" "list"] (subvec rest (- n 2))))
          (let [name (name-of rest 2)]
            (if (= :get (:method req))
              (tags-list store name)
              (http/method-not-allowed)))

          :else (http/not-found "unknown OCI route"))))))
