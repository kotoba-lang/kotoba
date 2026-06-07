-- SQLMesh audit: mv_natural_person_vital_stats invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_natural_person_count_positive,
  model dev.mv_natural_person_vital_stats,
  dialect postgres,
  description 'person_count must be > 0 (group rows imply at least one cohort person).'
);
SELECT *
FROM dev.mv_natural_person_vital_stats
WHERE person_count <= 0;

---

AUDIT (
  name assert_natural_person_vital_status_known,
  model dev.mv_natural_person_vital_stats,
  dialect postgres,
  description 'vital_status must be one of alive/deceased/unknown when non-null.'
);
SELECT *
FROM dev.mv_natural_person_vital_stats
WHERE vital_status IS NOT NULL
  AND vital_status NOT IN ('alive', 'deceased', 'unknown');
