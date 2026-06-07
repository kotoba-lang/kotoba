-- Telecom LI access audit summary: lawful intercept access event counts per role/kind.
MODEL (
  name dev.mv_telecom_li_access_audit_summary,
  kind FULL,
  dialect postgres,
  description 'Per (accessor_role, access_kind, record_kind): access count from LI access audit.',
  grain [accessor_role, access_kind, record_kind],
  tags [telecom, li, access_audit]
);

SELECT
  accessor_role,
  access_kind,
  record_kind,
  COUNT(*) AS access_count
FROM vertex_telecom_li_access_audit
GROUP BY accessor_role, access_kind, record_kind
