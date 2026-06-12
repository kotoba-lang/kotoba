-- Telecom NPN PNI inventory: per-PLMN PNI slice counts.
MODEL (
  name dev.mv_telecom_npn_pni_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (hosting_plmn_id, snssai, isolation_kind, sla_tier, status): PNI slice count.',
  grain [hosting_plmn_id, snssai, isolation_kind, sla_tier, status],
  tags [telecom, npn, pni, slice]
);

SELECT
  hosting_plmn_id,
  snssai,
  isolation_kind,
  sla_tier,
  status,
  COUNT(*) AS slice_count
FROM vertex_telecom_npn_pni_slice
GROUP BY hosting_plmn_id, snssai, isolation_kind, sla_tier, status
