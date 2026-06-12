-- State profile status: flat projection of state profile records.
MODEL (
  name dev.mv_state_profile_status,
  kind FULL,
  dialect postgres,
  description 'Flat projection of vertex_state_profile (repo, rkey, iso3, name, region, indexed_at).',
  grain [repo, rkey],
  tags [state, profile, status]
);

SELECT
  repo,
  rkey,
  iso3,
  name,
  region,
  indexed_at
FROM vertex_state_profile
