-- SQLMesh audit: mv_iryo_los_by_drg_daily invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_iryo_los_ordered,
  model dev.mv_iryo_los_by_drg_daily,
  dialect postgres,
  description 'min_los_days <= avg_los_days <= max_los_days.'
);
SELECT *
FROM dev.mv_iryo_los_by_drg_daily
WHERE min_los_days > avg_los_days
   OR avg_los_days > max_los_days;

---

AUDIT (
  name assert_iryo_los_nonnegative,
  model dev.mv_iryo_los_by_drg_daily,
  dialect postgres,
  description 'min_los_days must be >= 0 (length of stay cannot be negative).'
);
SELECT *
FROM dev.mv_iryo_los_by_drg_daily
WHERE min_los_days < 0;
