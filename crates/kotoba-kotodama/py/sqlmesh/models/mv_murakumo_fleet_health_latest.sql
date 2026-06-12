-- Murakumo fleet health latest: most recent health snapshot row.
MODEL (
  name dev.mv_murakumo_fleet_health_latest,
  kind FULL,
  dialect postgres,
  description 'Latest fleet health snapshot from vertex_murakumo_fleet_health.',
  grain [],
  tags [murakumo, fleet, health, latest]
);

SELECT *
FROM vertex_murakumo_fleet_health
WHERE indexed_at = (SELECT MAX(indexed_at) FROM vertex_murakumo_fleet_health)
