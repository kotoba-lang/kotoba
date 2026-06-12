-- SQLMesh audit: mv_open_power_open_outages invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_power_outage_count_positive,
  model dev.mv_open_power_open_outages,
  dialect postgres,
  description 'open_outage_count must be > 0 (group rows imply at least one open outage).'
);
SELECT *
FROM dev.mv_open_power_open_outages
WHERE open_outage_count <= 0;

---

AUDIT (
  name assert_power_customers_affected_nonnegative,
  model dev.mv_open_power_open_outages,
  dialect postgres,
  description 'total_customers_affected must be >= 0.'
);
SELECT *
FROM dev.mv_open_power_open_outages
WHERE total_customers_affected < 0;
