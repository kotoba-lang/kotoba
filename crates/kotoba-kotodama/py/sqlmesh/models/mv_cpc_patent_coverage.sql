-- CPC patent coverage: aggregated patent match count per CPC code.
MODEL (
  name dev.mv_cpc_patent_coverage,
  kind FULL,
  dialect postgres,
  description 'Per CPC code: matched prefix hits, distinct patent count, and latest published_at from mv_cpc_patent_prefix_match.',
  grain [cpc_code],
  tags [cpc, patent, coverage, tsukuru]
);

SELECT
  cpc_code,
  MAX(cpc_name) AS cpc_name,
  MAX(subclass_code) AS subclass_code,
  MAX(tsukuru_process) AS tsukuru_process,
  MAX(patent_hint_csv) AS patent_hint_csv,
  COUNT(*) AS matched_prefix_hits,
  COUNT(DISTINCT patent_vertex_id) AS matched_patent_count,
  MAX(published_at) AS latest_published_at
FROM mv_cpc_patent_prefix_match
GROUP BY cpc_code
