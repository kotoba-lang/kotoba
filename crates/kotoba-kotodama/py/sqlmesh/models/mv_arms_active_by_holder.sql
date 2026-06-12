-- Active or checked-out firearms with holder DID from edge_arms_firearm_to_holder.
MODEL (
  name dev.mv_arms_active_by_holder,
  kind FULL,
  dialect postgres,
  description 'Active/checked-out firearms joined with holder DID via edge_arms_firearm_to_holder.',
  grain [firearm_vid],
  tags [arms, firearm, holder, active]
);

SELECT
  e.dst         AS holder_did,
  f.vertex_id   AS firearm_vid,
  f.make,
  f.model,
  f.caliber,
  f.category,
  f.status,
  e.since       AS held_since
FROM edge_arms_firearm_to_holder e
JOIN vertex_arms_firearm f ON f.vertex_id = e.src
WHERE f.status IN ('active', 'checked_out')
