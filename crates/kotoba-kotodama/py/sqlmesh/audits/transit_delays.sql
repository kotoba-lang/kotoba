-- SQLMesh audit: mv_open_transit_active_delays invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_transit_delay_count_positive,
  model dev.mv_open_transit_active_delays,
  dialect postgres,
  description 'active_delay_count must be > 0 (group rows imply at least one active delay).'
);
SELECT *
FROM dev.mv_open_transit_active_delays
WHERE active_delay_count <= 0;

---

AUDIT (
  name assert_transit_max_delay_nonnegative,
  model dev.mv_open_transit_active_delays,
  dialect postgres,
  description 'max_delay_minutes must be >= 0.'
);
SELECT *
FROM dev.mv_open_transit_active_delays
WHERE max_delay_minutes < 0;
