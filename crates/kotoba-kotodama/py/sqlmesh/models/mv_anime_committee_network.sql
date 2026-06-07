-- Anime committee network: production committees per legal entity.
MODEL (
  name dev.mv_anime_committee_network,
  kind FULL,
  dialect postgres,
  description 'Count of distinct committees per legal entity from edge_anime_committee_member.',
  grain [legal_entity_did],
  tags [anime, committee, network, legal_entity]
);

SELECT
  cm.dst_vid AS legal_entity_did,
  COUNT(DISTINCT cm.src_vid) AS committee_count
FROM edge_anime_committee_member cm
GROUP BY cm.dst_vid
