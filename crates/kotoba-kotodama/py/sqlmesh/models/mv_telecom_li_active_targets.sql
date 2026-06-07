-- Telecom LI active targets: lawful intercept target counts per identifier kind and status.
MODEL (
  name dev.mv_telecom_li_active_targets,
  kind FULL,
  dialect postgres,
  description 'Per (identifier_kind, status): LI target count from vertex_telecom_li_target.',
  grain [identifier_kind, status],
  tags [telecom, li, target]
);

SELECT
  identifier_kind,
  status,
  COUNT(*) AS target_count
FROM vertex_telecom_li_target
GROUP BY identifier_kind, status
