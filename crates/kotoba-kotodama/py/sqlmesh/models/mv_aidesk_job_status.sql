-- AI desk design job counts grouped by actor, status, and license tier.
MODEL (
  name dev.mv_aidesk_job_status,
  kind FULL,
  dialect postgres,
  description 'Per-actor aidesk design job counts by status and license_tier with last activity timestamp.',
  grain [actor_did, status, license_tier],
  tags [aidesk, design, job, status, license]
);

SELECT
  j.actor_did,
  j.status,
  j.license_tier,
  COUNT(*) AS job_count,
  MAX(j.created_at) AS last_activity
FROM vertex_aidesk_design_job j
GROUP BY j.actor_did, j.status, j.license_tier
