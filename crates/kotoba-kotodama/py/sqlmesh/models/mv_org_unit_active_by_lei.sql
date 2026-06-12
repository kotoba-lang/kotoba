-- Org unit active by LEI: active org unit counts per LEI and org type.
MODEL (
  name dev.mv_org_unit_active_by_lei,
  kind FULL,
  dialect postgres,
  description 'Per (lei, org_type): active unit count and latest valid_from from vertex_org_unit.',
  grain [lei, org_type],
  tags [org_unit, lei, active]
);

SELECT
  lei,
  org_type,
  COUNT(*) AS unit_count,
  MAX(valid_from) AS latest_valid_from
FROM vertex_org_unit
WHERE status = 'active'
GROUP BY lei, org_type
