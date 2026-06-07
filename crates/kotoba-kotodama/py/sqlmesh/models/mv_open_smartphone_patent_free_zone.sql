-- Open smartphone patent free zone: SEPs with active blocker status and known expiry.
MODEL (
  name dev.mv_open_smartphone_patent_free_zone,
  kind FULL,
  dialect postgres,
  description 'Active blocker SEPs with non-null expiry_date for patent-free zone analysis.',
  grain [vertex_id],
  tags [open_smartphone, patent, sep, blocker]
);

SELECT
  vertex_id,
  patent_no,
  holder_did,
  rat,
  expiry_date,
  blocker_status
FROM vertex_open_smartphone_patent_sep
WHERE expiry_date IS NOT NULL
  AND blocker_status = 'active'
