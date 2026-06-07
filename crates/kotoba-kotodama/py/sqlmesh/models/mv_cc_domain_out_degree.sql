-- CC domain out-degree: outgoing link count per source domain.
MODEL (
  name dev.mv_cc_domain_out_degree,
  kind FULL,
  dialect postgres,
  description 'Per source domain DID: outgoing edge count and total link count from edge_links_to_domain.',
  grain [domain_did],
  tags [cc, domain, out_degree, links, crawl]
);

SELECT
  src_vid AS domain_did,
  COUNT(*) AS out_degree,
  SUM(count) AS total_links
FROM edge_links_to_domain
GROUP BY src_vid
