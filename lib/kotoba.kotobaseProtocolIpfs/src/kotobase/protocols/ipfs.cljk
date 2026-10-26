(ns kotobase.protocols.ipfs
  "ipfs gateway projection over the shared block space
  (ADR-2607171700, KRP §3.3 Content).

  GET /ipfs/{cid} serves the block stored by kotobase.protocols.blocks.
  GET /ipni/v1/ad/{cid} serves the same block plane at the IPNI
  publisher path (ADR-2608160300). `{cid}` is the advertisement CID,
  not the content CID. GET /ipni/v1/head serves the block named by
  optional ctx `:ipni-head-cid`. Missing head is 404 — not an empty
  200. This namespace does not require ipni and does not sign.

  Retrieval addrs stay /ipfs/{cid}. Publisher addrs must hit /ipni/v1/ad/{cid}.
  Putting a gateway-only origin in an announce 404s the chain.

  The HTTP surface is READ-ONLY by design — the same blast-radius
  principle that split gftdcojp/net-kotobase-ipfs out of net-kotobase
  (ADR-2607072000): a public gateway only ever needs read access.
  Writes go through the library fn `blocks/put-block!` inside an
  authenticated deploy shell.

  AUTHORITY NOTE: the public `ipfs.kotobase.net` route is owned by
  gftdcojp/net-kotobase-ipfs (ADR-2607072000). This handler is the
  portable, self-hosted/local-first equivalent (fleet peers, browser
  workers, tests); serving it on that hostname would need that repo to
  adopt it — non-authoritative until then. Host `ipfs.<apex>` already
  delivers every path to this handler. Single-origin `/ipni/` on the
  apex needs a router prefix in kotobase-protocol-core.

  Content-Type is sanitized through an allowlist (same convention as
  net-kotobase's archive-serving path): anything else degrades to
  application/octet-stream so a stored block can never become an
  executable HTML/SVG origin by accident."
  (:require [kotobase.protocols.blocks :as blocks]
            [kotobase.protocols.http :as http]))

(def content-type-allowlist
  #{"text/plain" "text/plain; charset=utf-8"
    "application/json" "application/cbor"
    "application/vnd.ipld.raw" "application/vnd.ipld.car"
    "application/vnd.ipld.dag-cbor" "application/vnd.ipld.dag-json"
    "application/octet-stream"
    "image/png" "image/jpeg" "image/gif" "image/webp"
    "video/mp4" "audio/mpeg" "model/gltf-binary"})

(defn sanitize-content-type [ct]
  (if (contains? content-type-allowlist ct) ct "application/octet-stream"))

(defn- serve-block
  "Read one CID from the block plane. `cid` is whatever the caller
  asked for — content or advertisement. This helper does not rewrite it."
  [ctx req cid extra-headers]
  (if-let [b (blocks/get-block ctx cid)]
    (cond-> (http/response 200
                           (merge {"content-type" (sanitize-content-type (:content-type b))
                                   "etag" (str "\"" cid "\"")
                                   "cache-control" "public, max-age=29030400, immutable"}
                                  extra-headers)
                           (when (= :get (:method req)) (:bytes b)))
      (= "base64" (:encoding b)) (assoc :body-encoding :base64))
    (http/not-found (str "block not found: " cid))))

(defn handle
  "IPFS gateway + IPNI publisher handler. Serves GET/HEAD /ipfs/{cid},
  /ipni/v1/ad/{cid}, and /ipni/v1/head from ctx's block plane — the
  `:blocks` port when the shell supplies one, the `:store` document
  collection otherwise (kotobase.protocols.blocks). `:ipni-head-cid`
  is the advertisement-chain tip, optional."
  [ctx req]
  (let [segs (http/segments (:path req))]
    (cond
      (not (#{:get :head} (:method req)))
      (http/method-not-allowed)

      (and (= "ipfs" (first segs)) (= 2 (count segs)))
      (let [cid (second segs)]
        (serve-block ctx req cid {"x-ipfs-path" (str "/ipfs/" cid)}))

      (and (= 4 (count segs))
           (= "ipni" (first segs))
           (= "v1" (second segs))
           (= "ad" (nth segs 2)))
      (let [cid (nth segs 3)]
        (serve-block ctx req cid {}))

      (= ["ipni" "v1" "head"] segs)
      (if-let [head-cid (:ipni-head-cid ctx)]
        (serve-block ctx req head-cid {})
        (http/not-found "ipni head not published"))

      (= "ipns" (first segs))
      (http/text 501 "ipns not implemented (mutable heads resolve via KRP signed heads)")

      :else (http/not-found))))
