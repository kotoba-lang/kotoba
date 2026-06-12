-- Sekkei stale reviews: design revisions awaiting approval.
MODEL (
  name dev.mv_sekkei_stale_reviews,
  kind FULL,
  dialect postgres,
  description 'Per drawing revision: revisions in pending-approval status with revisor metadata.',
  grain [drawing_id, rev_no],
  tags [sekkei, design, revision, review]
);

SELECT
  drawing_id,
  rev_no,
  revised_by_did,
  revised_at
FROM vertex_sekkei_revision
WHERE status = 'pending-approval'
