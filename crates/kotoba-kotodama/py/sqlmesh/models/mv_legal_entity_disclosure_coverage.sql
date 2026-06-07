-- Legal entity disclosure coverage: 5-axis disclosure score per company DID.
MODEL (
  name dev.mv_legal_entity_disclosure_coverage,
  kind FULL,
  dialect postgres,
  description 'Per company: filings, fact, ownership, trade rollups and disclosure_coverage_score (0-1).',
  grain [company_did],
  tags [legal_entity, disclosure, coverage]
);

WITH filing_counts AS (
  SELECT
    company_did,
    COUNT(*) AS filings_count,
    MAX(_seq) AS last_filing_seq
  FROM vertex_company_filing
  WHERE company_did IS NOT NULL
  GROUP BY company_did
),
fact_rollup AS (
  SELECT
    company_did,
    COUNT(*) AS fact_count,
    MAX(CASE
      WHEN LOWER(fact_name) IN ('revenue', 'sales', 'net_sales', 'sales_revenue', 'revenue_total')
      THEN 1 ELSE 0
    END) AS has_revenue_fact,
    MAX(CASE
      WHEN LOWER(fact_name) IN ('employee_count', 'employees', 'headcount', 'number_of_employees')
      THEN 1 ELSE 0
    END) AS has_employee_fact
  FROM vertex_company_fact
  WHERE company_did IS NOT NULL
  GROUP BY company_did
),
ownership_rollup AS (
  SELECT
    src_vid AS company_did,
    COUNT(*) AS subsidiaries_count
  FROM edge_legal_entity_owns
  WHERE src_vid IS NOT NULL
  GROUP BY src_vid
),
trade_rollup AS (
  SELECT
    src_vid AS company_did,
    COUNT(*) AS trade_edge_count
  FROM edge_legal_entity_trades_with
  WHERE src_vid IS NOT NULL
  GROUP BY src_vid
)
SELECT
  le.vertex_id AS company_did,
  le.name,
  le.country,
  le.jurisdiction,
  le.source,
  COALESCE(fc.filings_count, 0) AS filings_count,
  COALESCE(fr.fact_count, 0) AS fact_count,
  COALESCE(fr.has_revenue_fact, 0) AS has_revenue_fact,
  COALESCE(fr.has_employee_fact, 0) AS has_employee_fact,
  COALESCE(or1.subsidiaries_count, 0) AS subsidiaries_count,
  COALESCE(tr.trade_edge_count, 0) AS trade_edge_count,
  COALESCE(fc.last_filing_seq, 0) AS last_filing_seq,
  (
    COALESCE(CASE WHEN fc.filings_count > 0 THEN 1 ELSE 0 END, 0) +
    COALESCE(CASE WHEN fr.has_revenue_fact > 0 THEN 1 ELSE 0 END, 0) +
    COALESCE(CASE WHEN fr.has_employee_fact > 0 THEN 1 ELSE 0 END, 0) +
    COALESCE(CASE WHEN or1.subsidiaries_count > 0 THEN 1 ELSE 0 END, 0) +
    COALESCE(CASE WHEN tr.trade_edge_count > 0 THEN 1 ELSE 0 END, 0)
  )::DOUBLE PRECISION / 5.0 AS disclosure_coverage_score
FROM vertex_legal_entity le
LEFT JOIN filing_counts fc ON fc.company_did = le.vertex_id
LEFT JOIN fact_rollup fr ON fr.company_did = le.vertex_id
LEFT JOIN ownership_rollup or1 ON or1.company_did = le.vertex_id
LEFT JOIN trade_rollup tr ON tr.company_did = le.vertex_id
