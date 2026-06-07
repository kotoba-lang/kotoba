-- SQLMesh audit: mv_open_road_open_incidents invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_road_incident_count_positive,
  model dev.mv_open_road_open_incidents,
  dialect postgres,
  description 'open_incident_count must be > 0 (group rows imply at least one open incident).'
);
SELECT *
FROM dev.mv_open_road_open_incidents
WHERE open_incident_count <= 0;

---

AUDIT (
  name assert_road_total_delay_nonnegative,
  model dev.mv_open_road_open_incidents,
  dialect postgres,
  description 'total_delay_minutes must be >= 0.'
);
SELECT *
FROM dev.mv_open_road_open_incidents
WHERE total_delay_minutes < 0;
