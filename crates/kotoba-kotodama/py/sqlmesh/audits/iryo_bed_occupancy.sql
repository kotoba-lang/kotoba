-- SQLMesh audit: mv_iryo_bed_occupancy_now invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_iryo_occupied_le_total,
  model dev.mv_iryo_bed_occupancy_now,
  dialect postgres,
  description 'occupied_beds must not exceed total_beds.'
);
SELECT *
FROM dev.mv_iryo_bed_occupancy_now
WHERE occupied_beds > total_beds;

---

AUDIT (
  name assert_iryo_utilization_bounded,
  model dev.mv_iryo_bed_occupancy_now,
  dialect postgres,
  description 'utilization must be in [0, 1].'
);
SELECT *
FROM dev.mv_iryo_bed_occupancy_now
WHERE utilization < 0 OR utilization > 1;
