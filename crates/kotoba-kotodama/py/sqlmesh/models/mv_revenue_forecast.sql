-- Revenue forecast: expected uplift and earliest horizon per revenue stream.
MODEL (
  name dev.mv_revenue_forecast,
  kind FULL,
  dialect postgres,
  description 'Per revenue stream: current/target MRR, expected uplift (confidence-weighted), earliest horizon months.',
  grain [stream_code],
  tags [revenue, forecast, strategy, mrr]
);

SELECT
  rs.stream_code,
  rs.display_name,
  rs.current_mrr_jpy,
  rs.target_mrr_jpy,
  rs.status,
  SUM(gr.monthly_expected_jpy * gr.confidence_bps / 10000) AS expected_uplift_monthly,
  MIN(gr.horizon_months) AS earliest_horizon_months
FROM vertex_revenue_stream rs
LEFT JOIN edge_generates_revenue gr ON gr.dst_vid = rs.vertex_id
GROUP BY rs.stream_code, rs.display_name, rs.current_mrr_jpy, rs.target_mrr_jpy, rs.status
