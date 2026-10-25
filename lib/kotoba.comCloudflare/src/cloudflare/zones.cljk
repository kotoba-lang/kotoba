(ns cloudflare.zones
  "Cloudflare zone listing + DNS records (read-only). REST v4, JVM-only.

  W6 product-shell: pure REST path/query via kotoba zones_path_core
  (+ workers_path list-zones/dns base strings for parity)."
  (:require [cloudflare.client :as client]
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :zones-path)

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

(defn list-zones-path
  "REST path for zone listing (no query). JVM: kotoba `list-zones-path`."
  []
  (o 'list-zones-path []))

(defn list-zones-request-path
  "Path+query string list-zones passes to rest! (`/zones?per_page=50`).
   JVM: kotoba `list-zones-request-path`."
  []
  (o 'list-zones-request-path []))

(defn dns-records-path
  "REST path for DNS records under a zone. JVM: kotoba `dns-records-path`."
  [zone-id]
  (o-record 'dns-records-path {:zone-id zone-id} [[:zone-id :string]]))

(def ^:private match-schema
  [:record :zones/match [[:expected :string] [:actual :string]]])

(def ^:private zone-name-schema
  [:record :zones/zone-name [[:zone-id :string] [:name :string]]])

(defn hostname-matches?
  "Exact hostname/name equality used by zone-by-name and domain filters.
   JVM: kotoba `hostname-matches?`. T5.2 native guest record."
  [expected actual]
  (= 1 (oracle/i64->host
        (o-record 'hostname-matches?
                  {:in (oracle/record match-schema
                                      {:expected expected :actual actual})}
                  [[:in :raw]]))))

#?(:clj
(defn list-zones
  ([] (list-zones {}))
  ([http-opts]
   ;; Path embeds per_page=50 (historical contract; zones_path_core SSoT).
   (client/rest! (list-zones-request-path) http-opts))))

#?(:clj
(defn zone-by-name
  "The zone map for `name` (e.g. \"itonami.cloud\"), or nil if not found /
  not accessible with the current token."
  ([name] (zone-by-name name {}))
  ([name http-opts]
   (first (filter #(hostname-matches? name (:name %)) (list-zones http-opts))))))

#?(:clj
(defn dns-records
  "DNS records for `zone-id`, optionally filtered by `name` (exact match,
  e.g. \"app.itonami.cloud\") via a `:name` key in `http-opts`. Requires a
  token with DNS read scope -- Workers/Pages custom-domain routing is a
  separate, usually-broader-scoped surface (see
  cloudflare.workers/custom-domains), so a DNS-scope-only token failing
  here doesn't mean the zone/host doesn't exist."
  ([zone-id] (dns-records zone-id {}))
  ([zone-id {:keys [name] :as http-opts}]
   (client/rest! (dns-records-path zone-id)
                (assoc http-opts :query (cond-> {} name (assoc :name name)))))))
