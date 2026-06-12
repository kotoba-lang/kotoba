-- Maps social profile status: profile counts per status.
MODEL (
  name dev.mv_maps_social_profile_status,
  kind FULL,
  dialect postgres,
  description 'Per status: profile count and latest updated_at from vertex_maps_social_profile.',
  grain [status],
  tags [maps, social, profile, status]
);

SELECT
  status,
  COUNT(*) AS profile_count,
  MAX(updated_at) AS latest_updated_at
FROM vertex_maps_social_profile
GROUP BY status
