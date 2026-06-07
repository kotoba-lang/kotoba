-- SQLMesh audit: mv_post_engagement invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_post_engagement_total_consistent,
  model dev.mv_post_engagement,
  dialect postgres,
  description 'total_engagement must equal like_count + repost_count.'
);
SELECT *
FROM dev.mv_post_engagement
WHERE total_engagement <> like_count + repost_count;

---

AUDIT (
  name assert_post_engagement_counts_nonnegative,
  model dev.mv_post_engagement,
  dialect postgres,
  description 'like_count and repost_count must be >= 0.'
);
SELECT *
FROM dev.mv_post_engagement
WHERE like_count < 0 OR repost_count < 0;
