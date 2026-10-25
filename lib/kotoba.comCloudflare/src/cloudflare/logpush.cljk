(ns cloudflare.logpush
  "Cloudflare Logpush job management (REST v4, JVM-only) -- the \"log\"
  half of this library's ingest-and-analyze design (cloudflare.analytics
  is the aggregate/GraphQL half).

  Scope, honestly stated: this namespace manages Logpush *jobs*
  (list/create/get/update/delete) -- it does NOT fetch or parse the actual
  log lines a job pushes. A Logpush job streams NDJSON to a destination
  you own (R2/S3/GCS/Azure/Splunk/...); reading and parsing that stream is
  destination-specific and deliberately out of scope here (an R2-backed
  consumer belongs in its own namespace/library once a project actually
  needs one, not speculatively built ahead of a real destination).

  Why this matters for analysis this library's first consumer couldn't do
  with cloudflare.analytics alone: GraphQL Analytics only has aggregates
  (counts by dimension) -- it cannot tell you what a SPECIFIC request's
  response body, exception, or trace looked like. gftdcojp/cloud-itonami
  hit exactly this wall investigating unexplained 499s on a specific path
  (net-kotobase#153, 2026-07-04): aggregate counts showed the 499s were
  real, but nothing in GraphQL Analytics could explain *why*. A Logpush
  job on the `http_requests` (or `workers_trace_events`, for Worker
  exceptions/logs specifically) dataset, once wired to a real destination,
  is the concrete next step for that kind of investigation.

  W6 product-shell: pure REST paths via kotoba logpush_path_core."
  (:require [cloudflare.client :as client]
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :logpush-path)

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

(defn datasets-path
  "REST path for Logpush datasets. JVM: kotoba `datasets-path`."
  [zone-id]
  (o-record 'datasets-path {:zone-id zone-id} [[:zone-id :string]]))

(defn jobs-path
  "REST path for Logpush jobs collection. JVM: kotoba `jobs-path`."
  [zone-id]
  (o-record 'jobs-path {:zone-id zone-id} [[:zone-id :string]]))

(defn job-path
  "REST path for one Logpush job. JVM: kotoba `job-path`."
  [zone-id job-id]
  (o-record 'job-path
            {:in (oracle/record
                  [:record :logpush/zone-job [[:zone-id :string] [:job-id :string]]]
                  {:zone-id zone-id :job-id job-id})}
            [[:in :raw]]))

#?(:clj
(defn datasets
  "Available Logpush dataset names for `zone-id` (e.g. \"http_requests\",
  \"workers_trace_events\", \"firewall_events\")."
  ([zone-id] (datasets zone-id {}))
  ([zone-id http-opts]
   (client/rest! (datasets-path zone-id) http-opts))))

#?(:clj
(defn jobs
  "Logpush jobs configured for `zone-id`."
  ([zone-id] (jobs zone-id {}))
  ([zone-id http-opts]
   (client/rest! (jobs-path zone-id) http-opts))))

#?(:clj
(defn create-job!
  "Create a Logpush job. `dataset` (e.g. \"http_requests\"),
  `destination-conf` (a destination URI your account controls, e.g. an R2
  bucket with the appropriate query-string credentials Cloudflare's docs
  specify), and optional `fields`/`sample`/`filter` (per Logpush's own job
  schema) via `opts`."
  ([zone-id dataset destination-conf] (create-job! zone-id dataset destination-conf {} {}))
  ([zone-id dataset destination-conf opts] (create-job! zone-id dataset destination-conf opts {}))
  ([zone-id dataset destination-conf opts http-opts]
   (client/rest! (jobs-path zone-id)
                (assoc http-opts
                       :method :post
                       :body (merge {:dataset dataset :destination_conf destination-conf :enabled true} opts))))))

#?(:clj
(defn delete-job!
  ([zone-id job-id] (delete-job! zone-id job-id {}))
  ([zone-id job-id http-opts]
   (client/rest! (job-path zone-id job-id)
                (assoc http-opts :method :delete)))))
