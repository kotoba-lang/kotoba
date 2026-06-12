-- Telecom eSIM pending SMDS events: SMDS events awaiting delivery.
MODEL (
  name dev.mv_telecom_esim_pending_smds_events,
  kind FULL,
  dialect postgres,
  description 'Per event_id: pending SMDS event metadata (eid, smdp, type, expiry).',
  grain [event_id],
  tags [telecom, esim, smds, pending]
);

SELECT
  event_id,
  eid,
  smdp_address,
  event_type,
  expires_at,
  status,
  org_id
FROM vertex_telecom_esim_smds_event
WHERE status = 'pending'
