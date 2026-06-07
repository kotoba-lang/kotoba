-- Telecom eSIM active profiles: enabled eSIM profiles.
MODEL (
  name dev.mv_telecom_esim_active_profiles,
  kind FULL,
  dialect postgres,
  description 'Per (eid, iccid): enabled eSIM profile metadata (mno, smdp, observed_at, org).',
  grain [eid, iccid],
  tags [telecom, esim, active, profile]
);

SELECT
  eid,
  iccid,
  mno,
  smdp_address,
  profile_state,
  observed_at,
  org_id
FROM vertex_telecom_esim_profile
WHERE profile_state = 'enabled'
