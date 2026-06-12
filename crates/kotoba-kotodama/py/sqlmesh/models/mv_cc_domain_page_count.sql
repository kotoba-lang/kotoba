-- CC domain page count: hosted page count per domain.
MODEL (
  name dev.mv_cc_domain_page_count,
  kind FULL,
  dialect postgres,
  description 'Per domain DID: count of hosted pages from edge_hosts_page.',
  grain [domain_did],
  tags [cc, domain, page, count, crawl]
);

SELECT
  src_vid AS domain_did,
  COUNT(*) AS page_count
FROM edge_hosts_page
GROUP BY src_vid
