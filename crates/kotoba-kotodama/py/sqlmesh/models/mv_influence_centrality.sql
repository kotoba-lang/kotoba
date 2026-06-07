-- Influence centrality: multi-source centrality scores per business person.
MODEL (
  name dev.mv_influence_centrality,
  kind FULL,
  dialect postgres,
  description 'Per person vertex_id: follower, patent, board, publication, award and media counts for centrality.',
  grain [vertex_id],
  tags [influence, centrality, business_person]
);

SELECT
  p.vertex_id,
  p.name,
  COALESCE(f.follower_count, 0) AS follower_count,
  COALESCE(pat.patent_count, 0) AS patent_count,
  COALESCE(b.board_count, 0) AS board_count,
  COALESCE(pub.publication_count, 0) AS publication_count,
  COALESCE(aw.award_count, 0) AS award_count,
  COALESCE(med.media_count, 0) AS media_count
FROM vertex_business_person p
LEFT JOIN (
  SELECT dst_vid, COUNT(*) AS follower_count FROM edge_follows GROUP BY dst_vid
) f ON f.dst_vid = p.vertex_id
LEFT JOIN (
  SELECT inventor_did, COUNT(*) AS patent_count FROM vertex_open_patent_patent GROUP BY inventor_did
) pat ON pat.inventor_did = p.vertex_id
LEFT JOIN (
  SELECT person_did, COUNT(*) AS board_count FROM edge_board_member GROUP BY person_did
) b ON b.person_did = p.vertex_id
LEFT JOIN (
  SELECT author_did, COUNT(*) AS publication_count FROM edge_authored_by GROUP BY author_did
) pub ON pub.author_did = p.vertex_id
LEFT JOIN (
  SELECT recipient_did, COUNT(*) AS award_count FROM vertex_award_recipient GROUP BY recipient_did
) aw ON aw.recipient_did = p.vertex_id
LEFT JOIN (
  SELECT subject_did, COUNT(*) AS media_count FROM vertex_media_mention GROUP BY subject_did
) med ON med.subject_did = p.vertex_id
