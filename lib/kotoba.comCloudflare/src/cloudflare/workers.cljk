(ns cloudflare.workers
  "Cloudflare Workers scripts, zone routes, and account-level Custom
  Domains (read-only). REST v4, JVM-only.

  `custom-domains` is the one that matters most in practice: it's what let
  this library's first consumer (gftdcojp/cloud-itonami) actually identify
  which Worker serves a given hostname when neither DNS records nor a
  Pages project's domain list had the answer -- `app.itonami.cloud` turned
  out to be bound to the `local-murakumo` Worker's Custom Domain, not a
  zone-level route or a Pages custom domain (ADR-0010, 2026-07-04). Check
  `custom-domains` before assuming a hostname with no DNS/Pages hit is
  unaccounted for.

  W6 product-shell: pure REST paths via kotoba workers_path_core."
  (:require [cloudflare.client :as client]
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :workers-path)

(defn- o
  "Call a pure export. Requires the shipped oracle on every platform (T6.4)."
  [export args]
  (oracle/require-ready! oid)
  (oracle/call oid export args))

(defn- o-record
  "T5.2: structural host map → call-record (requires shipped oracle)."
  [export host-map field-specs]
  (oracle/require-ready! oid)
  (oracle/call-record oid export host-map field-specs))

(defn zone-routes-path
  "REST path for zone-level Worker routes.
   JVM: kotoba `zone-routes-path`."
  [zone-id]
  (o-record 'zone-routes-path {:zone-id zone-id} [[:zone-id :string]]))

(defn custom-domains-path
  "REST path for account Workers Custom Domains.
   JVM: kotoba `custom-domains-path`."
  [account-id]
  (o-record 'custom-domains-path {:account-id account-id} [[:account-id :string]]))

(defn scripts-path
  "REST path for account Worker scripts metadata.
   JVM: kotoba `scripts-path`."
  [account-id]
  (o-record 'scripts-path {:account-id account-id} [[:account-id :string]]))

#?(:clj
(defn zone-routes
  "Worker routes for `zone-id` (classic zone-level route patterns, e.g.
  \"example.com/api/*\" -> a script). Does NOT include Custom Domains
  (see custom-domains) -- those are a newer, separate binding surface."
  ([zone-id] (zone-routes zone-id {}))
  ([zone-id http-opts]
   (client/rest! (zone-routes-path zone-id) http-opts))))

#?(:clj
(defn custom-domains
  "Account-level Workers Custom Domains: {:hostname :service :zone_name
  :environment :enabled ...} per binding. This is the account-wide list --
  filter client-side by :hostname/:zone_name/:service as needed; there is
  no server-side filter param for this endpoint."
  ([account-id] (custom-domains account-id {}))
  ([account-id http-opts]
   (client/rest! (custom-domains-path account-id) http-opts))))

#?(:clj
(defn scripts
  "Worker scripts (metadata only, not source) for `account-id`."
  ([account-id] (scripts account-id {}))
  ([account-id http-opts]
   (client/rest! (scripts-path account-id) http-opts))))
