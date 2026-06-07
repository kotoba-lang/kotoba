-- Telecom eSIM audit recent: eSIM audit events ordered by observation time.
MODEL (
  name dev.mv_telecom_esim_audit_recent,
  kind FULL,
  dialect postgres,
  description 'Per audit_id: eSIM audit details ordered by observed_at DESC.',
  grain [audit_id],
  tags [telecom, esim, audit]
);

SELECT
  audit_id,
  eid,
  profile_count,
  active_iccid,
  free_memory_bytes,
  last_contact_at,
  observed_at,
  org_id
FROM vertex_telecom_esim_audit
ORDER BY observed_at DESC
