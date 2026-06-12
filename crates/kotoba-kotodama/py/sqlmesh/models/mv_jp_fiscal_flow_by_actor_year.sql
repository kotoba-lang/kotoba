-- JP fiscal flow by actor year: fiscal flow totals per year, type, and actor pair.
MODEL (
  name dev.mv_jp_fiscal_flow_by_actor_year,
  kind FULL,
  dialect postgres,
  description 'Per (fiscal_year, flow_type, source_did, dest_did): flow count and total amount in JPY.',
  grain [fiscal_year, flow_type, source_did, dest_did],
  tags [jp, fiscal, flow, actor]
);

SELECT
  fiscal_year,
  flow_type,
  source_did,
  dest_did,
  COUNT(*) AS flow_count,
  SUM(amount_jpy) AS total_amount_jpy
FROM edge_jp_fiscal_flow
GROUP BY fiscal_year, flow_type, source_did, dest_did
