-- Open gas leaks: per-segment active leak summary.
MODEL (
  name dev.mv_open_gas_open_leaks,
  kind FULL,
  dialect postgres,
  description 'Per segment_vertex_id: open leak count, worst class, public notice flag, latest report.',
  grain [segment_vertex_id],
  tags [open_gas, leak, open]
);

SELECT
  segment_vertex_id,
  COUNT(*) AS open_leak_count,
  MIN(leak_class) AS worst_class,
  BOOL_OR(require_public_notice) AS any_public_notice,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_gas_leak
WHERE status = 'open'
GROUP BY segment_vertex_id
