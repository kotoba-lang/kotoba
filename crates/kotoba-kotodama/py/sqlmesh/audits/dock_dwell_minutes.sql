-- SQLMesh audit: mv_dock_dwell_minutes_15m invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_dock_dwell_completion_count_positive,
  model dev.mv_dock_dwell_minutes_15m,
  dialect postgres,
  description 'completion_count must be > 0 (group rows imply at least one closed dock job).'
);
SELECT *
FROM dev.mv_dock_dwell_minutes_15m
WHERE completion_count <= 0;

---

AUDIT (
  name assert_dock_dwell_avg_nonnegative,
  model dev.mv_dock_dwell_minutes_15m,
  dialect postgres,
  description 'avg_dwell_min must be >= 0 (durations are non-negative).'
);
SELECT *
FROM dev.mv_dock_dwell_minutes_15m
WHERE avg_dwell_min < 0;

---

AUDIT (
  name assert_dock_dwell_p95_ge_avg,
  model dev.mv_dock_dwell_minutes_15m,
  dialect postgres,
  description 'p95_dwell_min must be >= avg_dwell_min (P95 cannot be below the mean).'
);
SELECT *
FROM dev.mv_dock_dwell_minutes_15m
WHERE p95_dwell_min IS NOT NULL
  AND avg_dwell_min IS NOT NULL
  AND p95_dwell_min < avg_dwell_min;
