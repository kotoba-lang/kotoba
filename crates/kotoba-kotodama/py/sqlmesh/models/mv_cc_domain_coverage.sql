-- CC domain coverage: domain metadata joined with actor profile.
MODEL (
  name dev.mv_cc_domain_coverage,
  kind FULL,
  dialect postgres,
  description 'Per domain: domain metadata with optional actor handle and display name (LEFT JOIN vertex_actor on DID).',
  grain [domain_did],
  tags [cc, domain, coverage, actor, crawl]
);

SELECT
  d.vertex_id AS domain_did,
  d.domain,
  d.topics,
  d.performer_type,
  d.status,
  a.vertex_id AS actor_vertex_id,
  a.handle,
  a.display_name
FROM vertex_domain d
LEFT JOIN vertex_actor a ON a.did = d.did
