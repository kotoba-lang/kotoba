-- SQLMesh audit: mv_open_lei_ems_candidates invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_lei_ems_match_score_bounded,
  model dev.mv_open_lei_ems_candidates,
  dialect postgres,
  description 'match_score must be in [0, 1] (similarity score).'
);
SELECT *
FROM dev.mv_open_lei_ems_candidates
WHERE match_score IS NOT NULL
  AND (match_score < 0 OR match_score > 1);

---

AUDIT (
  name assert_lei_ems_lei_present,
  model dev.mv_open_lei_ems_candidates,
  dialect postgres,
  description 'lei must be NOT NULL (PK from LEI entity table).'
);
SELECT *
FROM dev.mv_open_lei_ems_candidates
WHERE lei IS NULL;
