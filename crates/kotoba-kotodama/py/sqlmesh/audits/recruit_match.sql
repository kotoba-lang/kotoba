-- SQLMesh audit: mv_recruit_cohort_match_candidate invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_recruit_match_score_bounded,
  model dev.mv_recruit_cohort_match_candidate,
  dialect postgres,
  description 'match_score must be in [0, 100] (sum of bounded sub-scores).'
);
SELECT *
FROM dev.mv_recruit_cohort_match_candidate
WHERE match_score < 0 OR match_score > 100;

---

AUDIT (
  name assert_recruit_demand_score_bounded,
  model dev.mv_recruit_cohort_match_candidate,
  dialect postgres,
  description 'demand_score must be in [0, 1] (used as 0..1 multiplier in match_score).'
);
SELECT *
FROM dev.mv_recruit_cohort_match_candidate
WHERE demand_score < 0 OR demand_score > 1;
