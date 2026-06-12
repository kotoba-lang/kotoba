-- SQLMesh audit: mv_open_adnetwork_campaign_funnel invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_adnetwork_funnel_monotonic,
  model dev.mv_open_adnetwork_campaign_funnel,
  dialect postgres,
  description 'clicks <= impressions and conversions <= clicks (funnel monotonicity).'
);
SELECT *
FROM dev.mv_open_adnetwork_campaign_funnel
WHERE clicks > impressions
   OR conversions > clicks;

---

AUDIT (
  name assert_adnetwork_funnel_rates_bounded,
  model dev.mv_open_adnetwork_campaign_funnel,
  dialect postgres,
  description 'ctr_pct and cvr_pct must be in [0, 100].'
);
SELECT *
FROM dev.mv_open_adnetwork_campaign_funnel
WHERE ctr_pct < 0 OR ctr_pct > 100
   OR cvr_pct < 0 OR cvr_pct > 100;
