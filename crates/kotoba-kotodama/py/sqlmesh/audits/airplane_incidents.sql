-- SQLMesh audit: mv_open_airplane_open_incidents invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_airplane_incident_count_positive,
  model dev.mv_open_airplane_open_incidents,
  dialect postgres,
  description 'open_incident_count must be > 0 (group rows imply at least one open incident).'
);
SELECT *
FROM dev.mv_open_airplane_open_incidents
WHERE open_incident_count <= 0;

---

AUDIT (
  name assert_airplane_aircraft_vid_present,
  model dev.mv_open_airplane_open_incidents,
  dialect postgres,
  description 'aircraft_vid must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_open_airplane_open_incidents
WHERE aircraft_vid IS NULL;
