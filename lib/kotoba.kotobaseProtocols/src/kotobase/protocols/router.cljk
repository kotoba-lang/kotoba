(ns kotobase.protocols.router
  "Host-based dispatch for the kotobase protocol surfaces
  (ADR-2607171700, ADR-2607172210):

    s3.<apex>       → kotobase.protocols.s3
    ipfs.<apex>     → kotobase.protocols.ipfs
    atproto.<apex>  → kotobase.protocols.atproto
    git.<apex>      → kotobase.protocols.git
    pinning.<apex>  → kotobase.protocols.ipfs-pinning
    issues.<apex>   → kotobase.protocols.issue

  plus a single-origin fallback for deploys that only own one
  hostname: /ipfs/*, /xrpc/* and /pins/* dispatch by their
  protocol-inherent prefixes (/pins is the exact path shape the
  ipfs.github.io pinning-services-api-spec itself uses, so it doubles
  as both the single-origin mount and the spec-native path — no
  stripping needed), /s3/*, /git/* and /issues/* by stripped mount
  prefixes.

  ROUTING NOTE — why `pinning` gets its own subdomain instead of
  reusing `ipfs`: kotobase.protocols.ipfs documents its HTTP surface as
  READ-ONLY BY DESIGN (blast-radius principle, ADR-2607072000) — GET on
  ipfs.<apex> is meant to always be side-effect-free. The Pinning
  Service API is a write surface (POST/DELETE /pins) that happens to
  share the same underlying block space; mounting it under the `ipfs`
  subdomain would blur that read-only invariant at the *routing* layer
  even though the handler code stays separate. A distinct `pinning`
  subdomain keeps 'ipfs.<apex> is always safe to GET' mechanically true,
  mirrors how real pinning services are actually deployed (a separate
  host/API from the gateway, e.g. Pinata's api.pinata.cloud/psa vs. a
  plain IPFS gateway), and gives a deploy shell one clean place to gate
  write-capable auth (the Pinning API's bearer token) without
  special-casing paths under a nominally read-only host.

  A deploy shell may add surfaces of its own through `ctx :surfaces`
  (label -> handler), and `:path-surfaces` (path prefix -> label) for
  the single-origin fallback. That is how the query-protocol surfaces
  (sparql/cypher/gremlin) reach production without this namespace
  depending on them: they live in their own repositories, and the
  shell that already depends on both composes them. Built-in surfaces
  win over injected ones, so a shell cannot quietly shadow `s3` or
  `git` with something else.

  The apex defaults to \"kotobase.net\" but is injectable — the same
  router serves a self-hosted mesh peer on any domain. This module
  plans routes; actually answering on *.kotobase.net DNS requires the
  deploy-shell ADR + credentials described in ADR-2607171700
  (:not-decided), and ipfs.kotobase.net stays owned by
  gftdcojp/net-kotobase-ipfs (ADR-2607072000)."
  (:require [kotoba.lang.text :as str]
            [kotobase.protocols.atproto :as atproto]
            [kotobase.protocols.git :as git]
            [kotobase.protocols.http :as http]
            [kotobase.protocols.ipfs :as ipfs]
            [kotobase.protocols.ipfs-pinning :as ipfs-pinning]
            [kotobase.protocols.issue :as issue]
            [kotobase.protocols.s3 :as s3]))

(def surfaces
  {"s3" s3/handle
   "ipfs" ipfs/handle
   "atproto" atproto/handle
   "git" git/handle
   "pinning" ipfs-pinning/handle
   "issues" issue/handle})

(defn surface-of
  "\"s3.kotobase.net\" + apex \"kotobase.net\" → \"s3\"; nil when host
  is not a single label in front of the apex."
  [host apex]
  (when (and host (str/ends-with? host (str "." apex)))
    (let [label (subs host 0 (- (count host) (inc (count apex))))]
      (when (and (seq label) (not (str/includes? label ".")))
        label))))

(defn- strip-prefix [req prefix]
  (assoc req :path (subs (:path req) (count prefix))))

(defn surfaces-for
  "Every surface this request may reach: the built-ins plus whatever the
  deploy shell injected. Built-ins are merged LAST — a shell adds surfaces,
  it does not redefine `s3` or `git` out from under the router."
  [ctx]
  (merge (:surfaces ctx) surfaces))

(defn handle
  "Route `req` to its protocol surface. ctx: {:store ... :now ...
  :apex \"kotobase.net\" :surfaces {label handler} :path-surfaces
  {prefix label}}."
  [{:keys [apex] :or {apex "kotobase.net"} :as ctx} req]
  (let [path (or (:path req) "")
        all (surfaces-for ctx)
        surface (surface-of (:host req) apex)
        mounted (some (fn [[prefix label]]
                        (when (str/starts-with? path prefix) (get all label)))
                      (:path-surfaces ctx))]
    (if (and (= :get (:method req)) (= "/health" path) (contains? all surface))
      (http/response 200
                     {"content-type" "application/edn; charset=utf-8"
                      "cache-control" "no-store"}
                     (pr-str {:ok true :service (keyword (str "kotobase.protocols/" surface))
                              :surface (keyword surface) :apex apex}))
      (if-let [handler (get all surface)]
        (handler ctx req)
      (cond
        ;; Injected single-origin mounts, checked before the built-in
        ;; prefixes so a shell can mount /sparql or /cypher on the one
        ;; hostname it owns. The prefix is NOT stripped: these protocols
        ;; specify their own absolute paths (SPARQL 1.1 Protocol, Neo4j's
        ;; /db/data/transaction/commit), and stripping would break the
        ;; handlers' own path checks.
        mounted (mounted ctx req)
        (str/starts-with? path "/ipfs/") (ipfs/handle ctx req)
        (str/starts-with? path "/ipni/") (ipfs/handle ctx req)
        (str/starts-with? path "/ipns/") (ipfs/handle ctx req)
        (str/starts-with? path "/xrpc/") (atproto/handle ctx req)
        (str/starts-with? path "/pins")  (ipfs-pinning/handle ctx req)
        (str/starts-with? path "/s3/")   (s3/handle ctx (strip-prefix req "/s3"))
        (str/starts-with? path "/git/")  (git/handle ctx (strip-prefix req "/git"))
        (str/starts-with? path "/issues/") (issue/handle ctx (strip-prefix req "/issues"))
        :else (http/not-found "no protocol surface for this host/path"))))))
