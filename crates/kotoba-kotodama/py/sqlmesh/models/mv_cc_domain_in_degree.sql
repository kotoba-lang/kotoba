-- CC domain in-degree: incoming link count per destination domain.
MODEL (
  name dev.mv_cc_domain_in_degree,
  kind FULL,
  dialect postgres,
  description 'Per destination domain DID: incoming edge count and total link count from edge_links_to_domain.',
  grain [domain_did],
  tags [cc, domain, in_degree, links, crawl]
);

SELECT
  dst_vid AS domain_did,
  COUNT(*) AS in_degree,
  SUM(count) AS total_links
FROM edge_links_to_domain
GROUP BY dst_vid
