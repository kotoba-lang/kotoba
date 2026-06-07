-- Science paper domain stats: per-(domain, year) paper count and citation aggregates.
MODEL (
  name dev.mv_science_paper_domain_stats,
  kind FULL,
  dialect postgres,
  description 'Per (domain, year): paper count, embedded count, linked count, avg citations.',
  grain [domain, year],
  tags [science, paper, domain, stats]
);

SELECT
  domain,
  year,
  COUNT(*) AS paper_count,
  COUNT(CASE WHEN status = 'embedded' THEN 1 END) AS embedded_count,
  COUNT(CASE WHEN status = 'linked' THEN 1 END) AS linked_count,
  AVG(citation_count) AS avg_citations
FROM vertex_scientific_paper
GROUP BY domain, year
