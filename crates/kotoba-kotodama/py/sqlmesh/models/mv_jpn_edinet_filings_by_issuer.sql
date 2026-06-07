-- JPN EDINET filings by issuer: published securities filing counts per issuer and doc type.
MODEL (
  name dev.mv_jpn_edinet_filings_by_issuer,
  kind FULL,
  dialect postgres,
  description 'Per (edinet_code, doc_type_code): filing count and latest submission for published filings.',
  grain [edinet_code, doc_type_code],
  tags [jpn, edinet, securities, filings]
);

SELECT
  edinet_code,
  doc_type_code,
  COUNT(*) AS filing_count,
  MAX(submitted_at) AS latest_submitted_at
FROM vertex_jpn_edinet_securities_filing
WHERE status = 'published'
GROUP BY edinet_code, doc_type_code
