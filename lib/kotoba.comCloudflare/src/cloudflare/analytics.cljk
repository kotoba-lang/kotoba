(ns cloudflare.analytics
  "Cloudflare zone Analytics API (GraphQL): daily traffic trend and
  per-path/device/country/status breakdown. Generalized from
  cloud-itonami.analytics (gftdcojp/cloud-itonami, ADR-0010) -- every
  function here takes an explicit `zone-tag`, no itonami-specific default.

  Two real Cloudflare datasets, with real differences worth knowing before
  using either:

  - `httpRequests1dGroups` (daily-report!): daily aggregate. Any date
    range works on every plan tier.
  - `httpRequestsAdaptiveGroups` (path-report!): per-request granularity
    (path/device/country/status). Free-plan lookback is capped at ~1 day
    -- a wider range fails with a real `quota` GraphQL error, not
    silently-truncated data. `host` is optional: filtering to one host can
    legitimately return zero rows if that host has no traffic in the
    window while the zone as a whole does (a real finding this library's
    first consumer hit, not a bug -- see gftdcojp/cloud-itonami ADR-0010's
    app.itonami.cloud discovery), so omit `host` to see the whole zone
    first before assuming a host-filtered zero means something is broken."
  (:require [kotoba.lang.text :as str]
            [cloudflare.client :as client]
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :analytics)
(def ^:private parse-oid :analytics-parse)

(defn- o
  "Call a pure export. Requires the shipped oracle on every platform (T6.4)."
  ([export args]
   (oracle/require-ready! oid)
   (oracle/call oid export args))
  ([oracle-id export args]
   (oracle/require-ready! oracle-id)
   (oracle/call oracle-id export args)))

(defn- o-record
  "T5.2: structural host map → call-record (requires shipped oracle)."
  ([export host-map field-specs]
   (oracle/require-ready! oid)
   (oracle/call-record oid export host-map field-specs))
  ([oracle-id export host-map field-specs]
   (oracle/require-ready! oracle-id)
   (oracle/call-record oracle-id export host-map field-specs)))

(def daily-query
  (o 'daily-query []))

(defn path-query
  "GraphQL query text for the per-path/device/country/status breakdown.
  `host?` controls whether the query declares/filters on $host at all --
  the caller (path-report-request) only passes a $host variable when a
  host filter was actually requested, so the query text and the variables
  must agree on whether $host exists.
   Kotoba `path-query` (T6.4 requires oracle)."
  [host?]
  (o-record 'path-query {:host? (if host? 1 0)} [[:host? :i64]]))

(defn daily-report-request
  [{:keys [zone-tag since until]}]
  {:query daily-query :variables {:zoneTag zone-tag :since since :until until}})

(defn path-report-request
  [{:keys [zone-tag since until host]}]
  {:query (path-query (some? host))
   :variables (cond-> {:zoneTag zone-tag :since since :until until}
                host (assoc :host host))})

(defn- groups [response dataset]
  (get-in response [:data :viewer :zones 0 (keyword dataset)]))

(defn parse-daily-report
  "{:ok? true :days [{:date :requests :page-views :uniques :bytes} ...]
  :totals {...}} sorted by date ascending, or {:ok? false :errors [...]}
  on a GraphQL-level error (never throws -- a quota/syntax error is data,
  not an exception, so callers can decide what to do with it).
   JVM: error gate via kotoba `report-ok?`; totals via host reduce (sum* available)."
  [response]
  (let [has-errors (if (seq (:errors response)) 1 0)
        ok? (= 1 (oracle/i64->host (o-record parse-oid 'report-ok? {:has-errors has-errors} [[:has-errors :i64]])))]
    (if-not ok?
      {:ok? false :errors (:errors response)}
      (let [rows (groups response "httpRequests1dGroups")
            days (->> rows
                      (map (fn [r] {:date (get-in r [:dimensions :date])
                                   :requests (get-in r [:sum :requests])
                                   :page-views (get-in r [:sum :pageViews])
                                   :uniques (get-in r [:uniq :uniques])
                                   :bytes (get-in r [:sum :bytes])}))
                      (sort-by :date))
            reqs (mapv :requests days)
            pvs (mapv :page-views days)
            uniqs (mapv :uniques days)
            bytes (mapv :bytes days)]
        {:ok? true
         :days days
         :totals {:requests (reduce + 0 reqs)
                  :page-views (reduce + 0 pvs)
                  :uniques (reduce + 0 uniqs)
                  :bytes (reduce + 0 bytes)}}))))

(defn path-report-rows
  "The raw per-group rows behind a path-report! response, before any
  tallying: [{:path :device :country :status :count} ...] or nil on a
  GraphQL-level error. `parse-path-report`'s :by-path/:by-device/etc. maps
  are a lossy summary of this -- a consumer that wants to persist/analyze
  per-request-group facts (e.g. transacting them as datoms for later
  Datalog queries, rather than only ever seeing pre-flattened aggregates)
  should use this, not parse-path-report's tallies."
  [response]
  (when-not (seq (:errors response))
    (->> (groups response "httpRequestsAdaptiveGroups")
         (mapv (fn [r] {:path (get-in r [:dimensions :clientRequestPath])
                       :device (get-in r [:dimensions :clientDeviceType])
                       :country (get-in r [:dimensions :clientCountryName])
                       :status (get-in r [:dimensions :edgeResponseStatus])
                       :count (:count r)})))))

(defn parse-path-report
  "{:ok? true :total :by-path :by-device :by-country :by-status} (each a
  {value -> count} map, tallied by summing :count across all matching
  rows) or {:ok? false :errors [...]}. A lossy summary of path-report-rows
  -- a consumer that wants the underlying per-group facts (e.g. to persist
  them, not just display a tally) should use path-report-rows instead.
   JVM: error gate via kotoba `report-ok?`; tally folds stay host maps."
  [response]
  (let [has-errors (if (seq (:errors response)) 1 0)
        ok? (= 1 (oracle/i64->host (o-record parse-oid 'report-ok? {:has-errors has-errors} [[:has-errors :i64]])))]
    (if-not ok?
      {:ok? false :errors (:errors response)}
      (let [rows (path-report-rows response)
            tally (fn [k] (reduce (fn [acc r] (update acc (get r k) (fnil + 0) (:count r))) {} rows))]
        {:ok? true
         :total (reduce + 0 (map :count rows))
         :by-path (tally :path)
         :by-device (tally :device)
         :by-country (tally :country)
         :by-status (tally :status)}))))

#?(:clj
(defn daily-report!
  ([opts] (daily-report! opts {}))
  ([opts http-opts] (parse-daily-report (client/graphql! (daily-report-request opts) http-opts)))))

#?(:clj
(defn path-report!
  ([opts] (path-report! opts {}))
  ([opts http-opts] (parse-path-report (client/graphql! (path-report-request opts) http-opts)))))

#?(:clj
(defn iso-date
  "ISO date string `days-ago` days before today -- a daily-report!
  :since/:until building block."
  [days-ago]
  (str (.minusDays (java.time.LocalDate/now) days-ago))))

#?(:clj
(defn iso-instant-hours-ago
  "ISO instant string `hours-ago` hours before now -- a path-report!
  :since/:until building block. Takes whole hours directly (not fractional
  days) -- an earlier version of this in cloud-itonami.analytics divided
  hours by 24.0 and passed the resulting double to Duration/ofDays, which
  takes a long and silently truncated to a zero-width range for any
  sub-24h window (ADR-0010, 2026-07-04)."
  [hours-ago]
  (str (.minus (java.time.Instant/now) (java.time.Duration/ofHours hours-ago)))))
