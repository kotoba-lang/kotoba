-- Telecom TSN shaper state: TSN shaper counts per kind/action/status.
MODEL (
  name dev.mv_telecom_tsn_shaper_state,
  kind FULL,
  dialect postgres,
  description 'Per (shaper_kind, action, status): TSN shaper count.',
  grain [shaper_kind, action, status],
  tags [telecom, tsn, shaper]
);

SELECT
  shaper_kind,
  action,
  status,
  COUNT(*) AS shaper_count
FROM vertex_telecom_tsn_shaper
GROUP BY shaper_kind, action, status
