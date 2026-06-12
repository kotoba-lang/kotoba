-- Patent coverage by year and jurisdiction: application and grant counts with avg novelty.
MODEL (
  name dev.mv_patent_coverage_by_year_jurisdiction,
  kind FULL,
  dialect postgres,
  description 'Per (jurisdiction, filing_year): application count, granted count, avg novelty score.',
  grain [jurisdiction, filing_year],
  tags [patent, coverage, year, jurisdiction, novelty]
);

SELECT
  jurisdiction,
  SUBSTRING(filing_date, 1, 4) AS filing_year,
  COUNT(*) AS app_count,
  COUNT(grant_date) AS granted_count,
  AVG(novelty_score) AS avg_novelty
FROM vertex_open_patent_patent
WHERE filing_date IS NOT NULL
GROUP BY jurisdiction, SUBSTRING(filing_date, 1, 4)
