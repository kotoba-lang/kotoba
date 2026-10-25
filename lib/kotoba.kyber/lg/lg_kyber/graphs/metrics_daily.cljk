(ns lg.lg-kyber.graphs.metrics-daily
  "kyber metrics_daily — daily KPI snapshot feeding bmc_agent. Faithful langgraph-clj
  port of graphs/metrics_daily.py.

  Pipeline: collect_oss → collect_cloud → collect_revenue → write_snapshot → report → END

  The four collect/write nodes go through the injected `:db-api` (lg.lg-kyber.db) — the
  asyncpg pool's fetch/fetchval/execute contract — so the whole graph compiles AND runs
  under bb when a db-api is injected (match-db for tests; a real PG binding in prod).
  `report` is a pure summary transform. Each DB read keeps the python's per-block
  try/except → default-to-0 semantics."
  (:require [langgraph.graph :as g]
            [cheshire.core :as json]
            [lg.lg-kyber.db :as db]
            [lg.lg-kyber.graphs.util :as u]))

(def ^:private oss-stars-sql
  "SELECT COUNT(*) FROM vertex_kyber_oss_event WHERE event_type = 'star' AND created_at >= NOW() - INTERVAL '30 days'")
(def ^:private oss-downloads-sql
  "SELECT COUNT(*) FROM vertex_kyber_oss_event WHERE event_type = 'download' AND created_at >= NOW() - INTERVAL '30 days'")
(def ^:private tenants-free-sql
  "SELECT COUNT(*) FROM vertex_kyber_tenant WHERE tier = 'free' AND status = 'active'")
(def ^:private tenants-paid-sql
  "SELECT COUNT(*) FROM vertex_kyber_tenant WHERE tier != 'free' AND status = 'active'")
(def ^:private api-calls-sql
  "SELECT COALESCE(SUM(api_call_count_24h), 0) FROM vertex_kyber_tenant WHERE status = 'active'")
(def ^:private mrr-sql
  "SELECT COALESCE(SUM(qty), 0) FROM vertex_kyber_billing_event WHERE metric = 'mrr_jpy' AND ts_ms >= EXTRACT(EPOCH FROM date_trunc('month', NOW())) * 1000")
(def ^:private leads-sql
  "SELECT COUNT(*) FROM vertex_kyber_lead WHERE outreach_status = 'new'")
(def ^:private snapshot-sql
  "INSERT INTO vertex_kyber_metrics_snapshot (snapshot_id, run_date, payload_json, created_at) VALUES ($1, $2, $3, $4)")

(defn collect-oss [state]
  (let [{:keys [fetchval]} (db/db-of state)
        today (u/today-iso)
        [stars downloads]
        (try [(long (or (fetchval oss-stars-sql) 0))
              (long (or (fetchval oss-downloads-sql) 0))]
             (catch #?(:clj Exception :default :default) _ [0 0]))]
    (merge state {"run_date" today "oss_stars_30d" stars "oss_downloads_30d" downloads})))

(defn collect-cloud [state]
  (let [{:keys [fetchval]} (db/db-of state)
        [free paid api]
        (try [(long (or (fetchval tenants-free-sql) 0))
              (long (or (fetchval tenants-paid-sql) 0))
              (long (or (fetchval api-calls-sql) 0))]
             (catch #?(:clj Exception :default :default) _ [0 0 0]))]
    (merge state {"cloud_tenants_free" free "cloud_tenants_paid" paid "cloud_api_calls_24h" api})))

(defn collect-revenue [state]
  (let [{:keys [fetchval]} (db/db-of state)
        [mrr leads]
        (try [(long (or (fetchval mrr-sql) 0))
              (long (or (fetchval leads-sql) 0))]
             (catch #?(:clj Exception :default :default) _ [0 0]))]
    (merge state {"cloud_mrr_jpy" mrr "leads_new" leads})))

(defn write-snapshot [state]
  (let [{:keys [execute]} (db/db-of state)
        snapshot {"oss_stars_30d"      (get state "oss_stars_30d" 0)
                  "oss_downloads_30d"  (get state "oss_downloads_30d" 0)
                  "cloud_tenants_free" (get state "cloud_tenants_free" 0)
                  "cloud_tenants_paid" (get state "cloud_tenants_paid" 0)
                  "cloud_mrr_jpy"      (get state "cloud_mrr_jpy" 0)
                  "cloud_api_calls_24h" (get state "cloud_api_calls_24h" 0)
                  "leads_new"          (get state "leads_new" 0)}]
    (try
      (execute snapshot-sql
               (str (random-uuid))
               (get state "run_date" (u/today-iso))
               (json/generate-string snapshot)
               (u/today-iso))
      (catch #?(:clj Exception :default :default) _ nil))
    state))

(defn report [state]
  (let [run-date (get state "run_date" "")
        summary (str "[" run-date "] kyber metrics: "
                     "oss_stars30d=" (get state "oss_stars_30d" 0) " "
                     "tenants=" (get state "cloud_tenants_free" 0) "F+"
                     (get state "cloud_tenants_paid" 0) "P "
                     "mrr=¥" (u/group-thousands (get state "cloud_mrr_jpy" 0)) " "
                     "leads_new=" (get state "leads_new" 0))]
    (merge state {"summary" summary})))

(defn build
  "Compile the metrics_daily StateGraph (collect_oss → collect_cloud → collect_revenue
  → write_snapshot → report → END)."
  []
  (-> (g/state-graph)
      (g/add-node :collect-oss collect-oss)
      (g/add-node :collect-cloud collect-cloud)
      (g/add-node :collect-revenue collect-revenue)
      (g/add-node :write-snapshot write-snapshot)
      (g/add-node :report report)
      (g/set-entry-point :collect-oss)
      (g/add-edge :collect-oss :collect-cloud)
      (g/add-edge :collect-cloud :collect-revenue)
      (g/add-edge :collect-revenue :write-snapshot)
      (g/add-edge :write-snapshot :report)
      (g/set-finish-point :report)
      (g/compile-graph)))

(def graph (build))

(defn run [input] (g/invoke graph input))
